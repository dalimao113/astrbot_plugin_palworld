#!/usr/bin/env bash
# =============================================================================
#  帕鲁服务器管家 · 一键安装脚本 (install.sh)
#  仓库: https://github.com/dalimao113/astrbot_plugin_palworld
#
#  面向纯小白: 一条命令部署 帕鲁服务器 + AstrBot + NapCat + 本插件,
#  已有环境则"体检 + 精准补配置"。
#
#  用法:
#    curl -fsSLo install.sh <raw>/install.sh         # 先下载，不直接管道执行
#    bash -n install.sh                              # 检查脚本语法
#    bash install.sh --dry-run                       # 演练，只看不改
#    bash install.sh                                 # 确认后正式执行
#
#  设计原则(务必保持):
#    1) dry-run: 只检测 + 打印将要做什么 + 显示 diff, 绝不写文件/不重建容器
#    2) 改已有 compose = 备份 + 只增不改(surgical append) + 显示 diff + 停下确认
#    3) 幂等: 重复跑不会重复装/重复补
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# 0. 全局常量与路径
# 默认值面向 1Panel + Ubuntu 部署;非该环境可用环境变量覆盖,例如:
#   ASTRBOT_DIR=/your/astrbot PAL_DIR=/your/palworld EXTERNAL_NET=your_net bash install.sh
# 详见 README「非 1Panel / 自定义路径安装」。
# ---------------------------------------------------------------------------
ASTRBOT_DIR="${ASTRBOT_DIR:-/opt/1panel/docker/compose/astrbot}"
ASTRBOT_COMPOSE="${ASTRBOT_DIR}/docker-compose.yml"
ASTRBOT_DATA="${ASTRBOT_DIR}/astrbot/data"
ASTRBOT_CMD_CONFIG="${ASTRBOT_DATA}/cmd_config.json"   # AstrBot 顶层配置(含 t2i 策略/端点), 首启后生成, 带 UTF-8 BOM
PLUGIN_DIR="${ASTRBOT_DATA}/plugins/astrbot_plugin_palworld"
PLUGIN_CONFIG="${ASTRBOT_DATA}/config/astrbot_plugin_palworld_config.json"

PAL_DIR="${PAL_DIR:-/opt/palworld}"
PAL_COMPOSE="${PAL_DIR}/compose.yaml"
PAL_ENV="${PAL_DIR}/.env"

PLUGIN_REPO="https://github.com/dalimao113/astrbot_plugin_palworld.git"
# yq 固定到已发布的不可变版本，并用该版本官方 checksums 校验后再安装。
# 可通过环境变量显式覆盖版本，但仍必须通过对应版本的官方 SHA-256 校验。
YQ_VERSION="${YQ_VERSION:-v4.53.3}"
YQ_INSTALL_PATH="${YQ_INSTALL_PATH:-/usr/local/bin/yq}"
YQ_MIRROR_PREFIXES=(
  ""
  "https://ghproxy.net/"
  "https://mirror.ghproxy.com/"
)
export PATH="/usr/local/bin:${PATH}"

EXTERNAL_NET="${EXTERNAL_NET:-astrbot_default}"   # 所有容器共享的外部网络(可 env 覆盖)

# 本地 t2i(文/HTML 转图片) 渲染服务的容器内端点: 插件所有卡片出图都走它。
# 不部署它 → AstrBot 只能用内置 playwright(慢) 或公共端点(常年 502), 出图延迟极高。
# (镜像名 soulter/astrbot-t2i-service:latest 硬编码在下方各 compose 模板块里)
T2I_ENDPOINT="http://astrbot-t2i:8999"   # astrbot 容器内走容器名访问, 比宿主 IP 稳

DRY_RUN="${DRY_RUN:-0}"
UPDATE_MODE="${UPDATE_MODE:-0}"
IS_FRESH_INSTALL="${IS_FRESH_INSTALL:-0}"
TS="$(date +%Y%m%d_%H%M%S)"

# 运行中收集给用户看的输入(dry-run 下用占位)
PAL_ADMIN_PASSWORD=""
PAL_SERVER_NAME=""
PAL_PLAYERS=""
ADMIN_QQ=""

# 所有普通临时文件都放进同一个私有目录。_mktemp 常在 $(...) 子进程中调用，不能依赖
# 子进程修改父进程数组；退出时清理整个私有目录才能保证 ERR/Ctrl-C/正常退出都不留残渣。
_TMP_DIR="$(command mktemp -d "${TMPDIR:-/tmp}/palworld-install.XXXXXX")"
_TARGET_TMP_FILES=()
_mktemp() { command mktemp "${_TMP_DIR}/file.XXXXXX"; }
_target_mktemp() {
  TARGET_TMP="$(command mktemp "${1}.tmp.XXXXXX")"
  _TARGET_TMP_FILES+=("$TARGET_TMP")
}
_cleanup_tmp() {
  if [ "${#_TARGET_TMP_FILES[@]}" -gt 0 ]; then
    rm -f -- "${_TARGET_TMP_FILES[@]}" 2>/dev/null || true
  fi
  if [ -n "${_TMP_DIR:-}" ]; then
    rm -rf -- "$_TMP_DIR" 2>/dev/null || true
  fi
}
trap _cleanup_tmp EXIT

# ---------------------------------------------------------------------------
# 日志 / 颜色
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
  C_RESET=$'\033[0m'; C_R=$'\033[31m'; C_G=$'\033[32m'; C_Y=$'\033[33m'
  C_B=$'\033[34m'; C_C=$'\033[36m'; C_BOLD=$'\033[1m'
else
  C_RESET=""; C_R=""; C_G=""; C_Y=""; C_B=""; C_C=""; C_BOLD=""
fi

log()   { printf '%s\n' "${C_C}▸ ${*}${C_RESET}"; }
ok()    { printf '%s\n' "${C_G}  ✓ ${*}${C_RESET}"; }
warn()  { printf '%s\n' "${C_Y}  ⚠ ${*}${C_RESET}"; }
err()   { printf '%s\n' "${C_R}  ✗ ${*}${C_RESET}" >&2; }
step()  { printf '\n%s\n' "${C_BOLD}${C_B}==== ${*} ====${C_RESET}"; }

# ---------------------------------------------------------------------------
# 错误陷阱: 出错时给可读中文提示, 而不是一串英文
# ---------------------------------------------------------------------------
on_error() {
  local code=$? line=${1:-?}
  err "脚本在第 ${line} 行出错 (退出码 ${code})。"
  err "常见原因: 网络不通 / 权限不足 / 磁盘满。"
  err "可以: ① 重新跑一遍(脚本是幂等的, 不会重复装);"
  err "      ② 先加 --dry-run 演练看卡在哪;"
  err "      ③ 把上面几行红字截图发群里求助。"
  exit "$code"
}
trap 'on_error $LINENO' ERR

# ---------------------------------------------------------------------------
# dry-run 包装器: 所有"会改动系统的动作"都必须经过它
#   run_write "<描述>" command args...
# dry-run 时只打印 [演练] 描述, 绝不执行
# ---------------------------------------------------------------------------
run_write() {
  local desc="$1"; shift
  if [ "$DRY_RUN" = "1" ]; then
    printf '%s\n' "${C_Y}  [演练] ${desc}${C_RESET}"
    printf '%s\n' "${C_Y}         → ${*}${C_RESET}"
    return 0
  fi
  log "执行: ${desc}"
  "$@"
}

# 把候选文件复制到目标同目录的临时文件，保留已有文件的权限/所有者后原子替换。
# 新文件使用调用方给出的 mode。拒绝目标符号链接，避免 root 安装脚本被路径劫持。
atomic_replace_file() {
  local source="$1" target="$2" mode="${3:-600}" staged
  if [ -L "$target" ]; then
    err "拒绝覆盖符号链接: ${target}"
    return 1
  fi
  mkdir -p "$(dirname "$target")"
  _target_mktemp "$target"; staged="$TARGET_TMP"
  cp -- "$source" "$staged"
  if [ -e "$target" ]; then
    chmod --reference="$target" "$staged"
    chown --reference="$target" "$staged"
  else
    chmod "$mode" "$staged"
  fi
  mv -f -- "$staged" "$target"
  rm -f -- "$source"
}

# 只读命令直接跑(检测用), 不需要包装
is_dry() { [ "$DRY_RUN" = "1" ]; }

# ---------------------------------------------------------------------------
# 确认提示: 危险动作前停下问 y/N。dry-run 下自动视为"否"并说明。
# ---------------------------------------------------------------------------
confirm() {
  local prompt="$1"
  if is_dry; then
    printf '%s\n' "${C_Y}  [演练] 此处本应询问: ${prompt} —— 演练模式默认【不应用】${C_RESET}"
    return 1
  fi
  local ans=""
  # 有可交互终端才问; 无 tty(cron / 无 -t 的 docker exec / CI / curl|bash 无终端)
  # 时绝不读 stdin(那是脚本管道本身), 危险/改动操作一律默认【不执行】。
  if { exec 3</dev/tty; } 2>/dev/null; then
    exec 3<&-
    read -r -p "${C_BOLD}${prompt} [y/N]: ${C_RESET}" ans < /dev/tty || true
    [[ "$ans" =~ ^[Yy]$ ]]
  else
    warn "无可交互终端,危险/改动操作默认不执行:${prompt}"
    return 1
  fi
}

prompt_value() {
  # prompt_value <提示语> <默认值> <是否隐藏输入0/1>
  # 注意: stdout 会被 $(...) 捕获作为返回值, 任何提示/告警必须走 stderr, 别污染返回值。
  local prompt="$1" def="${2:-}" hide="${3:-0}" ans=""
  if is_dry; then
    printf '%s\n' "${def:-<演练占位>}"
    return 0
  fi
  # 有可交互终端才读; 无 tty 时绝不读 stdin(避免 curl|bash 把脚本源码当输入), 直接返回默认值。
  if { exec 3</dev/tty; } 2>/dev/null; then
    exec 3<&-
    if [ "$hide" = "1" ]; then
      read -r -s -p "${prompt}: " ans < /dev/tty || true; echo >&2
    else
      read -r -p "${prompt}${def:+ [默认 ${def}]}: " ans < /dev/tty || true
    fi
    printf '%s\n' "${ans:-$def}"
  else
    printf '%s\n' "无可交互终端,「${prompt}」使用默认值。" >&2
    printf '%s\n' "$def"
  fi
}

# ---------------------------------------------------------------------------
# 备份 + 显示 diff + 确认 + 应用  (compose / env 通用)
#   confirm_and_apply <目标文件> <候选新文件> <本次修改说明>
# 已备份为 <文件>.bak.<时间戳>。用户确认后才覆盖。
# 返回 0 = 已应用, 1 = 用户取消 / 无变化 / dry-run
# ---------------------------------------------------------------------------
confirm_and_apply() {
  local target="$1" candidate="$2" note="$3"
  if [ -L "$target" ]; then
    err "拒绝覆盖符号链接目标: ${target}"
    rm -f "$candidate"
    return 1
  fi
  if diff -q "$target" "$candidate" >/dev/null 2>&1; then
    ok "「${note}」无需改动 (已符合要求)"
    rm -f "$candidate"
    return 1
  fi
  printf '\n%s\n' "${C_BOLD}拟对 ${target} 做如下修改 (${note}):${C_RESET}"
  printf '%s\n' "${C_C}--------------------------------------------------------------${C_RESET}"
  # 只展示差异, 绿加红减
  diff -u "$target" "$candidate" | sed \
    -e "s/^+.*/${C_G}&${C_RESET}/" \
    -e "s/^-.*/${C_R}&${C_RESET}/" || true
  printf '%s\n' "${C_C}--------------------------------------------------------------${C_RESET}"
  warn "以上 + 为新增行, - 为删除行。只会新增, 不会破坏你其它自定义配置。"

  if is_dry; then
    printf '%s\n' "${C_Y}  [演练] 不会应用以上修改。${C_RESET}"
    rm -f "$candidate"
    return 1
  fi
  if confirm "应用以上修改?"; then
    cp -a "$target" "${target}.bak.${TS}"
    ok "已备份原文件到 ${target}.bak.${TS}"
    atomic_replace_file "$candidate" "$target"
    ok "已应用修改。"
    return 0
  else
    warn "已跳过, 未改动 ${target}"
    rm -f "$candidate"
    return 1
  fi
}

# ---------------------------------------------------------------------------
# 【核心】YAML 序列精准追加 (只增不改, 不重排/不动注释/不动其它行)
#   yaml_append_seq_item <文件> <service> <key> <item> > 新内容
# 用 awk 在 services.<svc>.<key>: 序列块末尾插入一行 "- <item>",
# 其余字节原样保留。检测用 yq(见下), 写入用本函数, 避免 yq -i 整文件重排。
# ---------------------------------------------------------------------------
yaml_append_seq_item() {
  local file="$1" svc="$2" key="$3" item="$4"
  awk -v svc="$svc" -v key="$key" -v item="$item" '
    function indent(s){ match(s,/^ */); return RLENGTH }
    BEGIN{ in_services=0; in_svc=0; in_seq=0; svc_ind=-1; key_ind=-1; item_ind=-1; last=0 }
    {
      line=$0; ind=indent(line)
      if (line ~ /^services:[[:space:]]*$/){ in_services=1 }
      if (in_services && match(line, "^ +" svc ":[[:space:]]*$")){ in_svc=1; svc_ind=ind; in_seq=0; lines[NR]=line; next }
      if (in_svc && ind <= svc_ind && line ~ ("^ {" svc_ind "}[^ ]")){ in_svc=0 }
      if (in_svc && ind > svc_ind && match(line, "^ +" key ":[[:space:]]*$")){ in_seq=1; key_ind=ind; item_ind=-1; last=NR; lines[NR]=line; next }
      if (in_seq){
        if (line ~ /^[[:space:]]*$/){ lines[NR]=line; next }
        if (line ~ /^[[:space:]]*#/ && ind>key_ind){ lines[NR]=line; last=NR; next }
        if (ind>key_ind && line ~ /^ +- /){ if(item_ind<0) item_ind=ind; last=NR; lines[NR]=line; next }
        in_seq=0
      }
      lines[NR]=line
    }
    END{
      for(i=1;i<=NR;i++){
        print lines[i]
        if(i==last && last>0){
          pad=""; for(j=0;j<item_ind;j++) pad=pad" "
          print pad "- " item
        }
      }
    }
  ' "$file"
}

# yq 只读检测: services.<svc>.<key> 序列里是否已有 <item>
seq_has_item() {
  local file="$1" svc="$2" key="$3" item="$4"
  [ -n "$(yq ".services.${svc}.${key}[] | select(. == \"${item}\")" "$file" 2>/dev/null)" ]
}

# 服务是否存在
svc_exists() { yq -e ".services | has(\"${2}\")" "$1" >/dev/null 2>&1; }

# t2i 渲染服务是否已存在: 服务名叫 t2i, 或任意服务的 container_name 是 astrbot-t2i
t2i_exists() {
  local f="$1"
  svc_exists "$f" t2i && return 0
  yq -e '[.services[] | select(.container_name == "astrbot-t2i")] | length > 0' "$f" >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# 【核心】在 services: 块末尾"只增不改"地追加一个完整 service 块
#   yaml_append_service <文件> <块文件> > 新内容
# awk 定位 services: 块内最后一个"缩进非空行", 在其后原样插入 <块文件> 内容,
# 其余字节(注释/缩进/顶层 networks 段)全部保留, 不重排/不动其它服务。
# ---------------------------------------------------------------------------
yaml_append_service() {
  local file="$1" blockfile="$2"
  awk -v blockfile="$blockfile" '
    BEGIN{ in_services=0; last=0 }
    {
      lines[NR]=$0
      if ($0 ~ /^services:[[:space:]]*$/){ in_services=1; next }
      if (in_services){
        if ($0 ~ /^[^[:space:]#]/){ in_services=0 }        # 到达下一个顶层键 → 退出 services 段
        else if ($0 ~ /^[[:space:]]+[^[:space:]]/){ last=NR }  # 只认"缩进非空行"(排除空行/顶格注释)，避免插到 networks 注释之后
      }
    }
    END{
      for(i=1;i<=NR;i++){
        print lines[i]
        if(i==last && last>0){
          while((getline l < blockfile) > 0) print l
        }
      }
    }
  ' "$file"
}

# astrbot 容器是否在运行
astrbot_running() { docker ps --format '{{.Names}}' 2>/dev/null | grep -qx astrbot; }

# compose 的默认网络是否会与已存在的 astrbot_default 标签冲突:
# 未声明 external, 且该网络已存在但不是 compose 拥有(手动 create 的标签为空) →
# docker compose up 会报 "incorrect label ... expected default"。返回0=有风险需修。
astrbot_network_risky() {
  local f="$1"
  local ext; ext="$(yq '.networks.default.external' "$f" 2>/dev/null)"
  [ "$ext" = "true" ] && return 1                # 已声明 external, 安全
  docker network inspect "$EXTERNAL_NET" >/dev/null 2>&1 || return 1  # 网络不存在, compose 自建无冲突
  local lbl; lbl="$(docker network inspect "$EXTERNAL_NET" --format '{{index .Labels "com.docker.compose.network"}}' 2>/dev/null)"
  [ "$lbl" = "default" ] && return 1             # 本 compose 已拥有该网络, 安全(现有生产不动)
  return 0                                        # 网络已存在但非本 compose 拥有 → 冲突风险
}

# 把 astrbot_default 声明为外部网络(写进候选文件, 由 confirm_and_apply 落盘)。
# 无 networks 段 → 末尾追加整块(保留全文); 已有 networks 段 → 用 yq 精准设两个键。
patch_astrbot_network() {
  local cand="$1"
  if [ "$(yq '.networks' "$cand" 2>/dev/null)" = "null" ]; then
    printf '\n# 共享外部网络(脚本预建)。声明 external 避免与已存在同名网络标签冲突。\nnetworks:\n  default:\n    name: %s\n    external: true\n' "$EXTERNAL_NET" >> "$cand"
  else
    yq -i ".networks.default.name = \"$EXTERNAL_NET\" | .networks.default.external = true" "$cand"
  fi
}

# ---------------------------------------------------------------------------
# .env 键值确保 (幂等)
#   ensure_env_kv <候选env文件> <key> <期望值> <force: 1=值不同也强制改>
# 缺失 -> 追加; 存在且 force=1 且值不同 -> 改; 否则保留用户值。
# 注意: 只写候选文件, 真正落盘由 confirm_and_apply 处理。
# ---------------------------------------------------------------------------
ensure_env_kv() {
  local file="$1" key="$2" val="$3" force="${4:-0}"
  if grep -qE "^${key}=" "$file"; then
    if [ "$force" = "1" ]; then
      local cur; cur="$(grep -E "^${key}=" "$file" | head -1 | cut -d= -f2-)"
      if [ "$cur" != "$val" ]; then
        # 用 awk 精准替换该行, 不动其它
        awk -v k="$key" -v v="$val" 'BEGIN{FS=OFS="="} $1==k{print k"="v; next} {print}' "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
      fi
    fi
  else
    printf '%s=%s\n' "$key" "$val" >> "$file"
  fi
}

# ===========================================================================
# 阶段 0: 前置检查
# ===========================================================================
stage_precheck() {
  step "阶段 0 / 前置检查"

  if is_dry; then
    printf '%s\n' "${C_BOLD}${C_Y}"
    printf '%s\n' "  ╔══════════════════════════════════════════════════════════╗"
    printf '%s\n' "  ║   演练模式 (--dry-run)                                     ║"
    printf '%s\n' "  ║   只检测、只打印将要做什么、只显示 diff。                 ║"
    printf '%s\n' "  ║   ★ 不会写任何文件、不会重建容器、不会安装任何东西 ★     ║"
    printf '%s\n' "  ╚══════════════════════════════════════════════════════════╝"
    printf '%s\n' "${C_RESET}"
  fi

  # root / sudo
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      warn "当前不是 root。脚本需要管理员权限, 请改用: sudo bash install.sh"
    else
      err "需要 root 权限运行 (在 1Panel 宿主终端里通常已是 root)。"
    fi
    is_dry || exit 1
  else
    ok "已是 root 权限"
  fi

  # 系统版本
  if [ -r /etc/os-release ]; then
    # shellcheck source=/etc/os-release
    # shellcheck disable=SC1091
    . /etc/os-release
    if [ "${ID:-}" = "ubuntu" ]; then
      ok "系统: ${PRETTY_NAME:-Ubuntu}"
    else
      warn "当前系统不是 Ubuntu (${PRETTY_NAME:-未知})。脚本可继续, 但仅在 Ubuntu 24.04 充分验证过。"
    fi
  else
    warn "无法识别系统版本, 继续。"
  fi

  # 网络连通(测 github, 失败给国内提示)
  if curl -fsS -m 8 -o /dev/null https://github.com 2>/dev/null; then
    ok "网络连通 (github 可达)"
  else
    warn "访问 github 较慢或不通, 脚本会自动尝试国内加速镜像。"
  fi
}

# ===========================================================================
# 阶段 1: 系统依赖 + yq
# ===========================================================================
stage_deps() {
  step "阶段 1 / 系统依赖"
  local need=()
  for c in curl git jq openssl wget sha256sum; do
    command -v "$c" >/dev/null 2>&1 || need+=("$c")
  done
  # ca-certificates 没有独立命令, 用 dpkg 判断
  if ! dpkg -s ca-certificates >/dev/null 2>&1; then need+=("ca-certificates"); fi

  if [ "${#need[@]}" -eq 0 ]; then
    ok "基础依赖齐全 (curl/git/jq/openssl/wget/sha256sum/ca-certificates)"
  else
    warn "缺少: ${need[*]}"
    run_write "apt 安装缺失依赖" bash -c "apt-get update -y && apt-get install -y ${need[*]}"
  fi

  # yq (mikefarah / Go 版)
  if command -v yq >/dev/null 2>&1 && yq --version 2>/dev/null | grep -qi mikefarah; then
    ok "yq 已安装: $(yq --version 2>/dev/null)"
  else
    warn "未检测到 mikefarah/yq, 准备安装到 ${YQ_INSTALL_PATH}"
    install_yq
  fi
}

release_sha256() {
  # release_sha256 <asset> <checksums> <checksums_hashes_order>
  local asset="$1" checksums="$2" order="$3" sha_col expected
  sha_col="$(awk '$0 == "SHA-256" { print NR + 1; exit }' "$order")"
  expected="$(awk -v f="$asset" -v c="$sha_col" '$1 == f { print $c; exit }' "$checksums")"
  [[ "$sha_col" =~ ^[0-9]+$ && "$expected" =~ ^[0-9a-fA-F]{64}$ ]] || return 1
  printf '%s' "$expected"
}

install_yq() {
  local arch asset official_base checksums_url order_url
  if ! [[ "$YQ_VERSION" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    err "YQ_VERSION 格式无效: ${YQ_VERSION}（应为 vX.Y.Z）"
    exit 1
  fi
  case "$(uname -m)" in
    x86_64|amd64) arch="amd64" ;;
    aarch64|arm64) arch="arm64" ;;
    *)
      err "当前 CPU 架构 $(uname -m) 暂无受支持的 yq 安装包（仅支持 amd64/arm64）。"
      exit 1
      ;;
  esac
  asset="yq_linux_${arch}"
  official_base="https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}"
  checksums_url="${official_base}/checksums"
  order_url="${official_base}/checksums_hashes_order"

  if is_dry; then
    run_write "下载 ${YQ_VERSION}/${asset}、校验官方 SHA-256 并原子安装到 ${YQ_INSTALL_PATH}" true
    return 0
  fi

  local binary checksums order
  binary="$(_mktemp)"; checksums="$(_mktemp)"; order="$(_mktemp)"
  log "下载 yq ${YQ_VERSION} 官方校验清单"
  if ! curl -fsSL -m 30 "$checksums_url" -o "$checksums" \
      || ! curl -fsSL -m 30 "$order_url" -o "$order"; then
    err "无法下载 yq 官方校验清单，拒绝安装未验证二进制。"
    exit 1
  fi

  local prefix url expected actual
  if ! expected="$(release_sha256 "$asset" "$checksums" "$order")"; then
    err "yq 官方校验清单格式异常，找不到 ${asset} 的 SHA-256。"
    exit 1
  fi

  for prefix in "${YQ_MIRROR_PREFIXES[@]}"; do
    url="${prefix}${official_base}/${asset}"
    log "尝试下载 yq: ${url}"
    : > "$binary"
    if wget -q --timeout=25 "$url" -O "$binary" 2>/dev/null \
        || curl -fsSL -m 35 "$url" -o "$binary" 2>/dev/null; then
      actual="$(sha256sum "$binary" | awk '{print $1}')"
      if [ "${actual,,}" = "${expected,,}" ]; then
        atomic_replace_file "$binary" "$YQ_INSTALL_PATH" 755
        if "$YQ_INSTALL_PATH" --version 2>/dev/null | grep -qi 'mikefarah/yq'; then
          ok "yq 安装成功且 SHA-256 校验通过: $($YQ_INSTALL_PATH --version)"
          return 0
        fi
        err "yq 校验通过但版本检查失败，拒绝继续。"
        exit 1
      fi
      warn "下载文件 SHA-256 不匹配，拒绝安装并尝试下一个地址。"
    else
      warn "该地址下载失败，换下一个地址..."
    fi
  done
  err "yq 下载或校验失败，原有 yq（如有）未被覆盖。"
  exit 1
}

# ===========================================================================
# 阶段 2: Docker
# ===========================================================================
stage_docker() {
  step "阶段 2 / Docker"
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    ok "Docker + docker compose 已就绪: $(docker --version 2>/dev/null | head -1)"
    return 0
  fi
  warn "未检测到 Docker(或缺 compose 插件)。"
  if is_dry; then
    run_write "下载完整 Docker 官方安装脚本到临时文件后执行" sh "<临时文件>" --mirror Aliyun
    return 0
  fi
  local docker_installer; docker_installer="$(_mktemp)"
  log "下载 Docker 官方安装脚本(下载完成后再执行，国内使用 Aliyun 镜像)..."
  if curl -fsSL -m 60 https://get.docker.com -o "$docker_installer" \
      && sh "$docker_installer" --mirror Aliyun; then
    run_write "启用并启动 docker" systemctl enable --now docker
    ok "Docker 安装完成: $(docker --version)"
  else
    err "Docker 安装失败。请参考 https://docs.docker.com/engine/install/ubuntu/ 手动安装后重跑。"
    exit 1
  fi
}

# ===========================================================================
# 阶段 3: 1Panel 检查(不强装)
# ===========================================================================
stage_1panel() {
  step "阶段 3 / 1Panel"
  if command -v 1pctl >/dev/null 2>&1 || [ -d /opt/1panel ]; then
    ok "检测到 1Panel(或其目录 /opt/1panel)"
  else
    warn "未检测到 1Panel。本脚本按 1Panel 的目录布局工作。"
    warn "如需安装 1Panel, 可执行(可选):"
    warn "  curl -sSL https://resource.fit2cloud.com/1panel/package/v2/quick_start.sh -o q.sh && bash q.sh"
    warn "脚本会继续, 并按标准路径 ${ASTRBOT_DIR} 创建所需目录。"
  fi
}

# ===========================================================================
# 阶段 4: AstrBot + NapCat
# ===========================================================================
stage_astrbot() {
  step "阶段 4 / AstrBot + NapCat"
  if [ -f "$ASTRBOT_COMPOSE" ]; then
    ok "已存在 AstrBot compose: ${ASTRBOT_COMPOSE} → 进入体检模式"
    healthcheck_astrbot
  else
    warn "未找到 ${ASTRBOT_COMPOSE} → 将用内置模板生成"
    generate_astrbot_compose
    # 全新生成: 容器刚首启, cmd_config.json 还没写出 → 等它出现再配置 t2i
    wait_for_astrbot_config
  fi
  # compose 里就绪 t2i 服务后, 把 AstrBot 自身的 t2i 配置指向它
  configure_astrbot_t2i
}

# ---------------------------------------------------------------------------
# 全新安装时 AstrBot 首启较慢, cmd_config.json 需等它生成后 configure_astrbot_t2i
# 才能写入。轮询等待该文件出现, 最多约 120 秒(每 3 秒探测一次); 超时则告警并继续。
# 注意: 脚本 set -euo pipefail, 探测用条件判断兜住, 不因失败触发 -e 退出。
# ---------------------------------------------------------------------------
wait_for_astrbot_config() {
  if is_dry; then return 0; fi
  local attempt
  for ((attempt = 0; attempt < 40; attempt++)); do
    if [ -f "$ASTRBOT_CMD_CONFIG" ]; then
      return 0
    fi
    sleep 3
  done
  warn "AstrBot 首启较慢, cmd_config.json 暂未生成, 稍后按阶段 7 去 WebUI 手动设置 t2i 端点。"
  return 0
}

# ---------------------------------------------------------------------------
# 把 AstrBot 的文转图配置指向本地 t2i 服务 (写 data/cmd_config.json 顶层):
#   t2i_strategy = "remote"; t2i_endpoint = "http://astrbot-t2i:8999"
# 关键约束:
#   - 该文件带 UTF-8 BOM, jq/python 直接读会报错 → 去 BOM 再改, 写回时保留 BOM。
#   - 全新安装时 AstrBot 尚未首启, 文件可能还不存在 → 不凭空造整份配置(易与默认结构
#     冲突), 改为跳过并由阶段 7 引导去 WebUI 设置。
#   - 幂等: 已是目标值则直接跳过, 不产生任何 diff。
# ---------------------------------------------------------------------------
configure_astrbot_t2i() {
  local target="$ASTRBOT_CMD_CONFIG"
  if [ ! -f "$target" ]; then
    warn "AstrBot 配置文件尚未生成: ${target}"
    warn "(AstrBot 容器首次启动后才会生成它; 稍后按阶段 7 提示去 WebUI 设置 t2i 端点即可。)"
    return 0
  fi

  # 去 BOM 供 jq 读取; 记录是否有 BOM, 写回时按原样保留
  local base has_bom=0
  base="$(_mktemp)"
  if [ "$(head -c3 "$target" | od -An -tx1 | tr -d ' \n')" = "efbbbf" ]; then has_bom=1; fi
  sed '1s/^\xEF\xBB\xBF//' "$target" > "$base"

  # base 必须是合法 JSON, 否则后面 jq 生成候选会非0退出 → set -e/ERR trap 直接中止整个安装。
  # 首启写一半/截断/磁盘满都可能产生非法 JSON, 这里兜住: 只跳过 t2i 配置, 不中止安装。
  if ! jq empty "$base" 2>/dev/null; then
    warn "AstrBot cmd_config.json 不是合法 JSON(可能首启写入未完成),跳过 t2i 端点配置;稍后按阶段 7 提示手动设置。"
    rm -f "$base"; return 0
  fi

  # 已是目标值 → 幂等跳过(避免 jq 重排导致的无谓 diff)
  local cs ce
  cs="$(jq -r '.t2i_strategy // empty' "$base" 2>/dev/null || true)"
  ce="$(jq -r '.t2i_endpoint // empty' "$base" 2>/dev/null || true)"
  if [ "$cs" = "remote" ] && [ "$ce" = "$T2I_ENDPOINT" ]; then
    ok "AstrBot 文转图已指向本地 t2i (remote → ${T2I_ENDPOINT})"
    rm -f "$base"; return 0
  fi

  # 生成候选: 只改这两个键, 其余键原样保留; 保留原 BOM
  local cand; cand="$(_mktemp)"
  { [ "$has_bom" = "1" ] && printf '\xEF\xBB\xBF'
    jq --arg ep "$T2I_ENDPOINT" '.t2i_strategy="remote" | .t2i_endpoint=$ep' "$base"
  } > "$cand"
  rm -f "$base"

  # 复用统一的 备份+diff+确认+dry-run 通道落盘
  confirm_and_apply "$target" "$cand" "把 AstrBot 文转图设为 remote → ${T2I_ENDPOINT}" || true
}

healthcheck_astrbot() {
  local f="$ASTRBOT_COMPOSE"
  # 前置: 两个 service 都在
  svc_exists "$f" astrbot || { err "compose 里缺 astrbot 服务, 不敢自动改, 请人工检查。"; return 0; }
  svc_exists "$f" napcat  || warn "compose 里缺 napcat 服务(QQ 客户端), 后面 QQ 登录会用不了。"

  # 用一个候选文件累积所有"缺失项"的追加, 最后统一 diff + 确认
  local cand; cand="$(_mktemp)"; cp "$f" "$cand"
  local changed=0

  # 1) astrbot 数据卷
  if seq_has_item "$cand" astrbot volumes "./astrbot/data:/AstrBot/data"; then
    ok "astrbot 数据卷 ./astrbot/data:/AstrBot/data 已挂载"
  else
    warn "缺 astrbot 数据卷 → 追加"
    yaml_append_seq_item "$cand" astrbot volumes "./astrbot/data:/AstrBot/data" > "${cand}.n" && mv "${cand}.n" "$cand" && changed=1
  fi

  # 2) docker.sock 只读挂载 (CPU/内存监控必需, 必查必补)
  if seq_has_item "$cand" astrbot volumes "/var/run/docker.sock:/var/run/docker.sock:ro"; then
    ok "docker.sock 只读挂载已存在 (容器资源监控可用)"
  else
    warn "缺 docker.sock 只读挂载 → 追加 (状态卡的 CPU/内存监控需要)"
    yaml_append_seq_item "$cand" astrbot volumes "/var/run/docker.sock:/var/run/docker.sock:ro" > "${cand}.n" && mv "${cand}.n" "$cand" && changed=1
  fi

  # 3) napcat 反向 WS 端口 3001
  if svc_exists "$f" napcat; then
    if seq_has_item "$cand" napcat ports "3001:3001"; then
      ok "napcat 反向 WS 端口 3001 已映射"
    else
      warn "缺 napcat 端口 3001 → 追加"
      yaml_append_seq_item "$cand" napcat ports "3001:3001" > "${cand}.n" && mv "${cand}.n" "$cand" && changed=1
    fi
  fi

  # 3b) astrbot WebUI 管理后台端口 6185 (浏览器进这个;漏了就进不去后台)
  if seq_has_item "$cand" astrbot ports "6185:6185"; then
    ok "astrbot WebUI 端口 6185 已映射"
  else
    warn "缺 astrbot WebUI 端口 6185 → 追加 (否则 6185 管理后台访问不到)"
    yaml_append_seq_item "$cand" astrbot ports "6185:6185" > "${cand}.n" && mv "${cand}.n" "$cand" && changed=1
  fi

  # 3c) t2i 渲染服务(缺则整块 surgical append, 根治出图延迟高/502)
  if t2i_exists "$cand"; then
    ok "t2i 渲染服务(astrbot-t2i)已在 compose 中"
  else
    warn "缺 t2i 渲染服务 → 追加整个 t2i 服务块 (否则卡片出图会又慢又常失败)"
    local t2iblk; t2iblk="$(_mktemp)"
    cat > "$t2iblk" <<'BLOCK'

  # t2i (文/HTML 转图片渲染服务) —— 插件所有卡片出图都走它。
  # astrbot 用容器名 http://astrbot-t2i:8999 内网访问, 避免走又慢又常 502 的公共端点。
  t2i:
    image: soulter/astrbot-t2i-service:latest
    container_name: astrbot-t2i
    restart: always
    ports:
      - "8999:8999"
    networks:
      - default
BLOCK
    yaml_append_service "$cand" "$t2iblk" > "${cand}.n" && mv "${cand}.n" "$cand" && changed=1
    rm -f "$t2iblk"
  fi

  # 4) save-tools 启动自愈(command 是复杂标量, 不自动改写, 仅提示)
  #    必须锁 0.24.0：palsave.py 解析器针对 0.24.0 打了 monkey-patch, 新版会解析失败。
  if yq '.services.astrbot.command' "$f" 2>/dev/null | grep -q 'palworld-save-tools==0.24.0'; then
    ok "astrbot 启动命令含 palworld-save-tools==0.24.0 自愈(存档功能可用)"
  elif yq '.services.astrbot.command' "$f" 2>/dev/null | grep -q 'palworld-save-tools'; then
    warn "astrbot 的 command 装了 palworld-save-tools 但【未锁版本】。"
    warn "  新版 save-tools 与本插件存档解析器(针对 0.24.0)不兼容, 会导致存档指令报错"
    warn "  (如 拉取/解析存档失败: 'CharacterSaveParameterMap')。请把 command 里的"
    warn "  palworld-save-tools 改为 palworld-save-tools==0.24.0, 并重装依赖后重载插件。"
  else
    warn "astrbot 的 command 未包含 palworld-save-tools 自愈。"
    warn "存档类指令(/帕鲁队伍 等)会报缺依赖。建议手动把 command 改为:"
    warn '  command: ["sh","-c","pip install --no-cache-dir palworld-save-tools==0.24.0 -i https://pypi.tuna.tsinghua.edu.cn/simple || true; exec python main.py"]'
    warn "(此项涉及自定义启动命令, 脚本不自动改写以免破坏你的配置)"
  fi

  # 5) 网络声明: 避免 astrbot_default 标签冲突
  #    (上次装到一半失败 / 旧模板缺 external 声明 会中招, 导致容器起不来)
  if astrbot_network_risky "$cand"; then
    warn "astrbot_default 网络未声明为 external, 会与已存在的同名网络标签冲突 → 修正"
    patch_astrbot_network "$cand"; changed=1
  else
    ok "astrbot 网络声明正常"
  fi

  if [ "$changed" = "1" ]; then
    if confirm_and_apply "$f" "$cand" "补齐 AstrBot/NapCat 关键挂载/端口/网络声明"; then
      ensure_external_network
      compose_up "$f"
    fi
  else
    rm -f "$cand"
    # 配置没问题, 但要确保容器真的在跑(上次可能装到一半失败, 容器没起来)
    if astrbot_running; then
      ok "AstrBot/NapCat 体检通过, 容器运行中"
    else
      warn "配置正常但 astrbot 容器未运行 → 启动"
      ensure_external_network
      compose_up "$f"
    fi
  fi
}

generate_astrbot_compose() {
  IS_FRESH_INSTALL=1
  run_write "创建目录 ${ASTRBOT_DATA} 等" mkdir -p "${ASTRBOT_DIR}/napcat/config" "${ASTRBOT_DIR}/napcat/qq" "${ASTRBOT_DATA}"
  local tmpl; tmpl="$(_mktemp)"
  cat > "$tmpl" <<'YAML'
services:
  # NapCat (QQ 客户端)
  napcat:
    image: mlikiowa/napcat-docker:latest
    container_name: napcat
    restart: always
    environment:
      - WS_ENABLE=true
      - HTTP_ENABLE=true
      - WEB_UI_ENABLE=true
      - WEB_UI_PORT=6099
      - TZ=Asia/Shanghai
    ports:
      - "6099:6099"
      - "3001:3001"
    volumes:
      - ./napcat/config:/app/napcat/config
      - ./napcat/qq:/app/.config/QQ
      - ./astrbot/data:/AstrBot/data

  # AstrBot (机器人核心)
  astrbot:
    image: soulter/astrbot:latest
    container_name: astrbot
    restart: always
    command: ["sh","-c","pip install --no-cache-dir palworld-save-tools==0.24.0 -i https://pypi.tuna.tsinghua.edu.cn/simple || true; exec python main.py"]
    depends_on:
      - napcat
    environment:
      - NAPCAT_HOST=napcat
      - NAPCAT_PORT=3001
      - TZ=Asia/Shanghai
    ports:
      - "6185:6185"    # WebUI 管理后台(浏览器进这个端口)
      - "6180:6180"
      - "6199:6199"
    volumes:
      - ./astrbot/data:/AstrBot/data
      - /var/run/docker.sock:/var/run/docker.sock:ro

  # t2i (文/HTML 转图片渲染服务) —— 插件所有卡片出图都走它。
  # astrbot 用容器名 http://astrbot-t2i:8999 内网访问, 避免走又慢又常 502 的公共端点。
  t2i:
    image: soulter/astrbot-t2i-service:latest
    container_name: astrbot-t2i
    restart: always
    ports:
      - "8999:8999"
    networks:
      - default

# 共享外部网络 astrbot_default(由脚本预先创建)。声明 external, 避免 compose
# 误以为该由自己创建而与已存在的同名网络标签冲突(帕鲁 compose 也接同一网络)。
networks:
  default:
    name: astrbot_default
    external: true
YAML
  if is_dry; then
    printf '%s\n' "${C_Y}  [演练] 将写出以下 compose 到 ${ASTRBOT_COMPOSE}:${C_RESET}"
    sed 's/^/    /' "$tmpl"
    rm -f "$tmpl"
    return 0
  fi
  atomic_replace_file "$tmpl" "$ASTRBOT_COMPOSE" 644
  ok "已生成 ${ASTRBOT_COMPOSE}"
  ensure_external_network
  compose_up "$ASTRBOT_COMPOSE"
}

# ===========================================================================
# 阶段 5: 帕鲁服务器
# ===========================================================================
stage_palworld() {
  step "阶段 5 / 帕鲁服务器"
  ensure_external_network
  if [ -f "$PAL_COMPOSE" ] && [ -f "$PAL_ENV" ]; then
    ok "已存在帕鲁 compose/.env → 进入体检模式"
    healthcheck_palworld
  else
    warn "未找到 ${PAL_COMPOSE} 或 .env → 用内置模板生成"
    generate_palworld
  fi
}

healthcheck_palworld() {
  # ---- .env 体检 ----
  local envc; envc="$(_mktemp)"; cp "$PAL_ENV" "$envc"

  # ADMIN_PASSWORD: 空则让用户输入或自动生成
  local curpw; curpw="$(grep -E '^ADMIN_PASSWORD=' "$envc" | head -1 | cut -d= -f2- || true)"
  if [ -z "$curpw" ]; then
    warn "帕鲁 ADMIN_PASSWORD 为空(REST 认证需要)"
    PAL_ADMIN_PASSWORD="$(prompt_value '请输入帕鲁管理员密码(留空则自动生成)' '' 1)"
    if [ -z "$PAL_ADMIN_PASSWORD" ]; then
      PAL_ADMIN_PASSWORD="$(openssl rand -hex 8 2>/dev/null || echo pal$RANDOM$RANDOM)"
      warn "已自动生成密码: ${PAL_ADMIN_PASSWORD} (请记好)"
    fi
    ensure_env_kv "$envc" ADMIN_PASSWORD "$PAL_ADMIN_PASSWORD" 1
  else
    PAL_ADMIN_PASSWORD="$curpw"
    ok "帕鲁 ADMIN_PASSWORD 已设置(将用于插件预填)"
  fi

  ensure_env_kv "$envc" REST_API_ENABLED true 1
  ensure_env_kv "$envc" REST_API_PORT   8212 1
  ensure_env_kv "$envc" EXIST_PLAYER_AFTER_LOGOUT True 1

  confirm_and_apply "$PAL_ENV" "$envc" "补齐帕鲁 .env 的 REST_API 开关/端口/管理密码" || true
  # 候选修改可能被用户取消；后续预填插件配置必须重新读取实际落盘值，不能使用未生效的新密码。
  PAL_ADMIN_PASSWORD="$(grep -E '^ADMIN_PASSWORD=' "$PAL_ENV" | head -1 | cut -d= -f2- || true)"
  if [ -z "$PAL_ADMIN_PASSWORD" ]; then
    warn "帕鲁 .env 的 ADMIN_PASSWORD 仍为空，后续将保留插件现有 admin_password，不写入空值。"
  fi

  # ---- compose 体检 ----
  local f="$PAL_COMPOSE"
  svc_exists "$f" palworld || { err "帕鲁 compose 缺 palworld 服务, 不敢自动改。"; return 0; }

  local cand; cand="$(_mktemp)"; cp "$f" "$cand"; local changed=0
  # 存档卷
  if seq_has_item "$cand" palworld volumes "./palworld:/palworld/"; then
    ok "帕鲁存档卷 ./palworld:/palworld/ 已挂载"
  else
    warn "缺帕鲁存档卷 → 追加"
    yaml_append_seq_item "$cand" palworld volumes "./palworld:/palworld/" > "${cand}.n" && mv "${cand}.n" "$cand" && changed=1
  fi
  # 外部网络(关键: 插件靠容器名 palworld-server 访问)
  local net; net="$(yq '.networks.default.name // ""' "$f" 2>/dev/null)"
  local ext; ext="$(yq '.networks.default.external // false' "$f" 2>/dev/null)"
  if [ "$net" = "$EXTERNAL_NET" ] && [ "$ext" = "true" ]; then
    ok "帕鲁已接入外部网络 ${EXTERNAL_NET} (可被插件访问)"
  else
    warn "帕鲁 compose 的 default 网络不是外部 ${EXTERNAL_NET}(当前 name=${net:-无}, external=${ext})。"
    warn "这决定插件能否用容器名 palworld-server:8212 访问帕鲁。请人工确认 networks 配置:"
    warn "  networks: { default: { name: ${EXTERNAL_NET}, external: true } }"
    warn "(网络是全局映射块, 结构因人而异, 脚本不自动改写以免破坏。)"
  fi

  if [ "$changed" = "1" ]; then
    if confirm_and_apply "$f" "$cand" "补齐帕鲁存档卷"; then
      compose_up "$f"
    fi
  else
    ok "帕鲁 compose 体检通过"
    rm -f "$cand"
  fi
  # 确保容器在运行：体检模式下容器可能被停/删(上次没起来), up -d 幂等(在跑=空操作, 没跑=拉起)
  compose_up "$f"
}

generate_palworld() {
  run_write "创建目录 ${PAL_DIR}/palworld" mkdir -p "${PAL_DIR}/palworld"
  PAL_ADMIN_PASSWORD="$(prompt_value '请输入帕鲁管理员密码(留空则自动生成)' '' 1)"
  if [ -z "$PAL_ADMIN_PASSWORD" ]; then
    PAL_ADMIN_PASSWORD="$(openssl rand -hex 8 2>/dev/null || echo pal$RANDOM$RANDOM)"
    warn "已自动生成帕鲁密码: ${PAL_ADMIN_PASSWORD} (请记好)"
  fi
  PAL_SERVER_NAME="$(prompt_value '服务器名称(显示在社区列表)' '帕鲁服务器' 0)"
  PAL_PLAYERS="$(prompt_value '最大玩家数(1-32)' '32' 0)"
  # 人数兜底：非 1-32 的纯数字则回退 32
  case "$PAL_PLAYERS" in
    ''|*[!0-9]*) PAL_PLAYERS=32 ;;
    *) [ "$PAL_PLAYERS" -ge 1 ] && [ "$PAL_PLAYERS" -le 32 ] || PAL_PLAYERS=32 ;;
  esac

  local ct; ct="$(_mktemp)"
  cat > "$ct" <<'YAML'
---
services:
  palworld:
    image: thijsvanloef/palworld-server-docker:latest
    restart: unless-stopped
    container_name: palworld-server
    stop_grace_period: 30s
    env_file:
      - ./.env
    ports:
      - "8211:8211/udp"
      - "27015:27015/udp"
      - "127.0.0.1:8212:8212/tcp"
    volumes:
      - ./palworld:/palworld/
    networks:
      - default

networks:
  default:
    name: astrbot_default
    external: true
YAML

  # 完整参数版 .env(内容取自 docs/DEPLOY.md 第 11 章参考, 每个参数上方一行中文注释)。
  # 用带引号 heredoc 当字面量写出, 避免 CROSSPLAY_PLATFORMS=(...) / cron 表达式等被 shell
  # 意外展开或 glob; 三个引导输入的值先写占位符, heredoc 之后再用 sed 替换成真实值。
  local et; et="$(_mktemp)"
  cat > "$et" <<'ENVEOF'
# Palworld 服务器配置 (.env) — 每项单独一行中文注释，改值后重新部署生效
# ⚠️ 注释必须单独成行，不能和值写同一行

# ════════ 容器 / 基础 ════════
# 时区
TZ=Asia/Shanghai
# 容器运行用户ID
PUID=1000
# 容器运行用户组ID
PGID=1000
# 游戏端口(UDP)
PORT=8211
# 查询端口(社区列表用UDP)
QUERY_PORT=27015
# 公开服拉满，官方上限就是 32
PLAYERS=__PLAYERS__
# 多线程(提升性能)
MULTITHREADING=true

# ════════ 服务器信息 ════════
# 服务器名(显示在社区列表)
SERVER_NAME=__SERVER_NAME__
# 服务器简介
SERVER_DESCRIPTION=欢迎来玩~

# ════════ 公开 / 密码 / 网络 ════════
# 显示在游戏内"社区服务器"列表
COMMUNITY=true
# 留空=完全开放，任何人直接进。注意：值和注释不能写在同一行，否则注释会被当成密码
SERVER_PASSWORD=
# 管理用，必须设且改掉，别留默认
ADMIN_PASSWORD=__ADMIN_PASSWORD__
# REST API / 玩家列表 / 认证
# 是否启用REST API(机器人管理需要)
REST_API_ENABLED=true
# REST API端口(只绑本机)
REST_API_PORT=8212
# 是否公开在线玩家列表
SHOW_PLAYER_LIST=true
# 是否记录玩家进出日志
ENABLE_PLAYER_LOGGING=true
# 是否启用账号认证
USEAUTH=true

# ════════ 跨平台 ════════
# 允许的跨平台(Steam/Xbox/PS5/Mac)
CROSSPLAY_PLATFORMS=(Steam,Xbox,PS5,Mac)

# ════════ 自动更新 ════════
# 开机时检查并更新游戏
UPDATE_ON_BOOT=true
# 公开服建议开，跟上客户端版本
AUTO_UPDATE_ENABLED=true
# 每小时第 5 分钟检查更新（避开每天 05:00 例行重启）
AUTO_UPDATE_CRON_EXPRESSION=5 * * * *
# 更新前提前几分钟通知
AUTO_UPDATE_WARN_MINUTES=5

# ════════ 自动重启 ════════
# 是否定时自动重启
AUTO_REBOOT_ENABLED=true
# 有人在线时不强制重启
AUTO_REBOOT_EVEN_IF_PLAYERS_ONLINE=false
# 重启前提前几分钟通知
AUTO_REBOOT_WARN_MINUTES=5
# 自动重启时间(cron表达式)
AUTO_REBOOT_CRON_EXPRESSION=0 5 * * *

# ════════ 备份 / 存档 ════════
# 是否自动备份存档
BACKUP_ENABLED=true
# 备份时间(cron表达式)
BACKUP_CRON_EXPRESSION=0 3 * * *
# 是否删除旧备份
DELETE_OLD_BACKUPS=true
# 备份保留天数
OLD_BACKUP_DAYS=30
# 自动存盘间隔(分钟)
AUTO_SAVE_SPAN=30.000000
# 玩家离线后角色/帕鲁/背包保留在存档，机器人才能离线查档案
EXIST_PLAYER_AFTER_LOGOUT=True

# ════════ ★ 经验 / 捕获 / 帕鲁数量 ════════
# 经验获取倍率(越大升级越快)
EXP_RATE=1.000000
# 帕鲁捕获成功率倍率
PAL_CAPTURE_RATE=1.000000
# 野生帕鲁刷新数量倍率
PAL_SPAWN_NUM_RATE=1.000000

# ════════ ★ 伤害倍率 ════════
# 帕鲁造成伤害倍率
PAL_DAMAGE_RATE_ATTACK=1.000000
# 帕鲁受到伤害倍率(越大越脆)
PAL_DAMAGE_RATE_DEFENSE=1.000000
# 玩家造成伤害倍率
PLAYER_DAMAGE_RATE_ATTACK=1.000000
# 玩家受到伤害倍率(越大越脆)
PLAYER_DAMAGE_RATE_DEFENSE=1.000000

# ════════ ★ 生命自动回复 ════════
# 玩家生命自动回复倍率
PLAYER_AUTO_HP_REGEN_RATE=1.000000
# 玩家睡觉时生命回复倍率
PLAYER_AUTO_HP_REGEN_RATE_IN_SLEEP=1.000000
# 帕鲁生命自动回复倍率
PAL_AUTO_HP_REGEN_RATE=1.000000
# 帕鲁在帕鲁箱中生命回复倍率
PAL_AUTO_HP_REGEN_RATE_IN_SLEEP=1.000000

# ════════ ★ 消耗 / 负重 / 耐久 ════════
# 玩家饱食度下降速度(越小越耐饿)
PLAYER_STOMACH_DECREASE_RATE=1.000000
# 玩家耐力下降速度
PLAYER_STAMINA_DECREASE_RATE=1.000000
# 帕鲁饱食度下降速度
PAL_STOMACH_DECREASE_RATE=1.000000
# 帕鲁耐力下降速度
PAL_STAMINA_DECREASE_RATE=1.000000
# 物品重量倍率(越小越能背)
ITEM_WEIGHT_RATE=1.000000
# 装备耐久损耗倍率
EQUIPMENT_DURABILITY_DAMAGE_RATE=1.000000

# ════════ ★ 时间 / 速度 / 孵蛋 ════════
# 白天时间流速倍率
DAYTIME_SPEEDRATE=1.000000
# 夜晚时间流速倍率
NIGHTTIME_SPEEDRATE=1.000000
# 帕鲁工作&建造速度倍率
WORK_SPEED_RATE=1.000000
# 帕鲁蛋孵化时间(小时, 越小越快, 想秒孵设0)
PAL_EGG_DEFAULT_HATCHING_TIME=72.000000

# ════════ ★ 掉落 ════════
# 采集物(树/矿等)掉落数量倍率
COLLECTION_DROP_RATE=1.000000
# 击杀敌人掉落数量倍率
ENEMY_DROP_ITEM_RATE=1.000000
# 地面掉落物数量上限
DROP_ITEM_MAX_NUM=3000
# 掉落物存在小时数
DROP_ITEM_ALIVE_MAX_HOURS=1.000000
# 地面便便数量上限
DROP_ITEM_MAX_NUM_UNKO=100

# ════════ ★ 采集物 ════════
# 采集物耐久倍率(越小越好砍)
COLLECTION_OBJECT_HP_RATE=1.000000
# 采集物再生速度倍率
COLLECTION_OBJECT_RESPAWN_SPEED_RATE=1.000000

# ════════ ★ 建筑 / 基地 ════════
# 建筑耐久倍率
BUILD_OBJECT_HP_RATE=1.000000
# 建筑受攻击伤害倍率
BUILD_OBJECT_DAMAGE_RATE=1.000000
# 建筑自然劣化速度(0=不劣化, 不用喂材料)
BUILD_OBJECT_DETERIORATION_DAMAGE_RATE=1.000000
# 全服基地数量上限
BASE_CAMP_MAX_NUM=128
# 单个基地工作帕鲁上限
BASE_CAMP_WORKER_MAX_NUM=15
# 每个公会基地数量上限
BASE_CAMP_MAX_NUM_IN_GUILD=4
# 单基地建筑数量上限(0=无限)
MAX_BUILDING_LIMIT_NUM=0
# 是否开启建造区域限制
BUILD_AREA_LIMIT=False

# ════════ 公会 ════════
# 公会最大人数
GUILD_PLAYER_MAX_NUM=20
# 公会全员离线时自动解散
AUTO_RESET_GUILD_NO_ONLINE_PLAYERS=False
# 自动解散的离线小时数
AUTO_RESET_GUILD_TIME_NO_ONLINE_PLAYERS=72.000000

# ════════ PvP / 公会对抗 ════════
# 是否开启PvP
IS_PVP=False
# 公开服防恶意 PK，先关玩家互伤
ENABLE_PLAYER_TO_PLAYER_DAMAGE=False
# 是否开启友军误伤
ENABLE_FRIENDLY_FIRE=False
# 是否允许进攻其他公会基地
ENABLE_DEFENSE_OTHER_GUILD_PLAYER=False
# 能否捡其他公会死亡掉落
CAN_PICKUP_OTHER_GUILD_DEATH_PENALTY_DROP=False
# 隐藏其他公会基地范围特效
INVISIBLE_OTHER_GUILD_BASE_CAMP_AREA_FX=False

# ════════ 难度 / 死亡惩罚 / 硬核 ════════
# 难度(None/Casual/Normal/Hard…)
DIFFICULTY=None
# 死亡惩罚(None不掉/Item掉物品/ItemAndEquipment掉物品装备/All全掉含帕鲁)
DEATH_PENALTY=All
# 硬核模式(死亡永久失去)
HARDCORE=False
# 硬核死亡后是否重建角色
CHARACTER_RECREATE_IN_HARDCORE=False
# 硬核下帕鲁是否也永久失去
PAL_LOST=False
# 长期不登录是否惩罚
ENABLE_NON_LOGIN_PENALTY=True

# ════════ 世界 / 探索 ════════
# 是否允许快速旅行(传送)
ENABLE_FAST_TRAVEL=True
# 是否地图选择出生点
IS_START_LOCATION_SELECT_BY_MAP=True
# 是否出现入侵者(突袭)
ENABLE_INVADER_ENEMY=True
# 是否出现掠食者头目帕鲁
ENABLE_PREDATOR_BOSS_PAL=True

# ════════ 帕鲁箱跨服传输 ════════
# 是否允许把帕鲁导出到全局帕鲁箱
ALLOW_GLOBAL_PALBOX_EXPORT=True
# 是否允许从全局帕鲁箱导入
ALLOW_GLOBAL_PALBOX_IMPORT=False

# ════════ 随机器 Randomizer ════════
# 随机器类型(None=关)
RANDOMIZER_TYPE=None
# 随机器种子
RANDOMIZER_SEED=""
# 随机器帕鲁等级是否随机
IS_RANDOMIZER_PAL_LEVEL_RANDOM=False

# ════════ 其它 / 杂项 ════════
# 空投补给间隔(分钟)
SUPPLY_DROP_SPAN=180
# 每分钟聊天发言上限
CHAT_POST_LIMIT_PER_MINUTE=10
# 是否启用便便(UNKO)
ACTIVE_UNKO=False
# 手柄瞄准辅助
ENABLE_AIM_ASSIST_PAD=True
# 键盘瞄准辅助
ENABLE_AIM_ASSIST_KEYBOARD=False
# 容器强制保存间隔(秒)
ITEM_CONTAINER_FORCE_MARK_DIRTY_INTERVAL=1.000000
# 物品腐败速度倍率
ITEM_CORRUPTION_MULTIPLIER=1.000000
# 实体同步距离(性能相关)
SERVER_REPLICATE_PAWN_CULL_DISTANCE=15000.000000
ENVEOF

  # 占位符 → 真实值。用 | 作分隔符; 先转义值里的 \ | & 以防特殊字符(如密码含 /|&)破坏替换。
  local esc_pw esc_name esc_players
  esc_pw="$(printf '%s' "$PAL_ADMIN_PASSWORD" | sed -e 's/[\\|&]/\\&/g')"
  esc_name="$(printf '%s' "$PAL_SERVER_NAME" | sed -e 's/[\\|&]/\\&/g')"
  esc_players="$(printf '%s' "$PAL_PLAYERS" | sed -e 's/[\\|&]/\\&/g')"
  sed -i \
    -e "s|__ADMIN_PASSWORD__|${esc_pw}|" \
    -e "s|__SERVER_NAME__|${esc_name}|" \
    -e "s|__PLAYERS__|${esc_players}|" "$et"

  if is_dry; then
    printf '%s\n' "${C_Y}  [演练] 将写出 ${PAL_COMPOSE}:${C_RESET}"; sed 's/^/    /' "$ct"
    printf '%s\n' "${C_Y}  [演练] 将写出 ${PAL_ENV} (密码已隐藏):${C_RESET}"; sed 's/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=******/' "$et" | sed 's/^/    /'
    rm -f "$ct" "$et"; return 0
  fi
  atomic_replace_file "$ct" "$PAL_COMPOSE" 644
  atomic_replace_file "$et" "$PAL_ENV" 600
  ok "已生成 ${PAL_COMPOSE} 和 ${PAL_ENV}"
  compose_up "$PAL_COMPOSE"
}

# ===========================================================================
# 阶段 6: 插件 + 预填配置
# ===========================================================================
stage_plugin() {
  step "阶段 6 / 安装插件 + 预填配置"
  if [ -d "${PLUGIN_DIR}/.git" ]; then
    ok "插件已存在 → git pull 更新"
    run_write "更新插件" git -C "$PLUGIN_DIR" pull --ff-only \
      || warn "插件 git pull 失败(可能本地改过插件文件), 已跳过更新; 可手动 git stash/reset 后重试或用 WebUI 更新。"
  elif [ -d "$PLUGIN_DIR" ]; then
    warn "插件目录已存在但不是 Git 安装，保留现有文件并跳过 clone。"
    warn "后续更新请使用 AstrBot WebUI「插件管理 → 更新」，或确认目录可替换后手动重装。"
  else
    run_write "克隆插件到 ${PLUGIN_DIR}" git clone --depth 1 "$PLUGIN_REPO" "$PLUGIN_DIR"
  fi

  # 收集 admin_qq：已配置(非空)则跳过询问，避免重复安装/更新时反复问
  local cur_qq_len=0
  if [ -f "$PLUGIN_CONFIG" ]; then
    cur_qq_len="$(sed '1s/^\xEF\xBB\xBF//' "$PLUGIN_CONFIG" | jq -r '(.admin_qq // []) | length' 2>/dev/null || echo 0)"
  fi
  if [ "${cur_qq_len:-0}" -gt 0 ]; then
    ok "管理员 QQ 已配置(admin_qq 非空)，跳过询问"
    ADMIN_QQ=""
  else
    ADMIN_QQ="$(prompt_value '请输入管理员 QQ 号(用于接收告警/授权指令)' '' 0)"
  fi

  prefill_plugin_config
}

prefill_plugin_config() {
  local cfgdir; cfgdir="$(dirname "$PLUGIN_CONFIG")"
  run_write "确保配置目录存在" mkdir -p "$cfgdir"

  # 组装 jq 过滤器: api_base/docker_container 总是写；密码仅在实际 .env 非空时写；
  # admin_qq 仅在本次提供新值时写。其余键一律保留。
  # jq 变量必须以原样字符串传给 jq。
  # shellcheck disable=SC2016
  local jqf='.api_base=$ab | .docker_container=$dc'
  local qq_json='[]'
  if [ -n "$PAL_ADMIN_PASSWORD" ]; then
    jqf="$jqf | .admin_password=\$pw"
  fi
  if [ -n "$ADMIN_QQ" ]; then
    qq_json="$(printf '%s' "$ADMIN_QQ" | jq -R 'split(" ")|map(select(length>0))')"
    jqf="$jqf | .admin_qq=\$qq"
  fi

  if is_dry; then
    printf '%s\n' "${C_Y}  [演练] 将预填插件配置 ${PLUGIN_CONFIG}:${C_RESET}"
    printf '%s\n' "${C_Y}    api_base=http://palworld-server:8212${C_RESET}"
    printf '%s\n' "${C_Y}    docker_container=palworld-server${C_RESET}"
    if [ -n "$PAL_ADMIN_PASSWORD" ]; then
      printf '%s\n' "${C_Y}    admin_password=(将使用帕鲁 .env 的同一密码，已隐藏)${C_RESET}"
    else
      printf '%s\n' "${C_Y}    admin_password=(帕鲁 .env 为空，保留现有值)${C_RESET}"
    fi
    if [ -n "$ADMIN_QQ" ]; then
      printf '%s\n' "${C_Y}    admin_qq=${qq_json}${C_RESET}"
    else
      printf '%s\n' "${C_Y}    admin_qq=(保留现有，不改)${C_RESET}"
    fi
    printf '%s\n' "${C_Y}    (写入时会先去除 UTF-8 BOM 再用 jq 合并, 保留其它键)${C_RESET}"
    return 0
  fi

  local base new cur; base="$(_mktemp)"; new="$(_mktemp)"; cur="$(_mktemp)"
  if [ -f "$PLUGIN_CONFIG" ]; then
    # 去 BOM 再交给 jq(否则 jq 报 Unexpected UTF-8 BOM)
    sed '1s/^\xEF\xBB\xBF//' "$PLUGIN_CONFIG" > "$base"
  else
    echo '{}' > "$base"
  fi
  if ! jq empty "$base" 2>/dev/null; then
    warn "插件配置不是合法 JSON，已保留原文件并跳过自动预填；请先在 WebUI 修复配置。"
    rm -f "$base" "$new" "$cur"
    return 0
  fi
  # 用同一 jq 排版归一化现有内容, 便于与新内容做等值比较(避免仅排版差异误判为有改动)
  jq '.' "$base" > "$cur" 2>/dev/null || cp "$base" "$cur"
  jq \
    --arg ab "http://palworld-server:8212" \
    --arg dc "palworld-server" \
    --arg pw "${PAL_ADMIN_PASSWORD:-}" \
    --argjson qq "$qq_json" \
    "$jqf" "$base" > "$new"
  if cmp -s "$cur" "$new"; then
    rm -f "$base" "$new" "$cur"
    ok "插件配置无需改动(内容一致), 跳过写入与备份。"
    return 0
  fi
  # 确有变化才备份并写入(避免每次运行都堆积 .bak 且不静默覆盖用户手改)
  [ -f "$PLUGIN_CONFIG" ] && cp -a "$PLUGIN_CONFIG" "${PLUGIN_CONFIG}.bak.${TS}"
  atomic_replace_file "$new" "$PLUGIN_CONFIG" 600
  rm -f "$base" "$cur"
  ok "插件配置已预填(api_base/docker_container，并按可用值更新密码和管理员 QQ)，其它键保留。"
}

# ===========================================================================
# 更新模式 (--update): 只拉最新插件与各镜像并重建, 不改配置/不重新提问
# ===========================================================================
stage_update() {
  step "更新模式 / 拉取最新插件与镜像"
  command -v docker >/dev/null 2>&1 || { err "未检测到 docker"; exit 1; }

  # 更新插件
  if [ -d "${PLUGIN_DIR}/.git" ]; then
    run_write "更新插件(git pull)" git -C "$PLUGIN_DIR" pull --ff-only \
      || warn "插件更新失败(可能本地有改动), 跳过, 仅更新镜像"
  elif [ -d "$PLUGIN_DIR" ]; then
    warn "插件目录非 git 安装, 跳过自动更新; 请用 AstrBot WebUI「插件管理→更新」或手动重装。"
  else
    warn "未找到插件目录 ${PLUGIN_DIR}, 请先正常安装再更新。"
  fi

  # 更新镜像并用新镜像重建容器
  local f
  for f in "$ASTRBOT_COMPOSE" "$PAL_COMPOSE"; do
    if [ -f "$f" ]; then
      run_write "拉取最新镜像 ($f)" docker compose -f "$f" pull \
        || warn "$f 更新失败, 跳过"
      run_write "用新镜像重建容器 ($f)" docker compose -f "$f" up -d \
        || warn "$f 更新失败, 跳过"
    else
      warn "未找到 $f, 跳过。"
    fi
  done

  ok "更新完成。若插件有更新, 请去 AstrBot WebUI「插件管理→重载插件」使其生效(镜像更新已随重建生效)。"
}

# ===========================================================================
# 公共: 外部网络 / compose 重建
# ===========================================================================
ensure_external_network() {
  if docker network inspect "$EXTERNAL_NET" >/dev/null 2>&1; then
    ok "外部网络 ${EXTERNAL_NET} 已存在"
  else
    warn "外部网络 ${EXTERNAL_NET} 不存在 → 创建"
    run_write "创建 docker 网络 ${EXTERNAL_NET}" docker network create "$EXTERNAL_NET"
  fi
}

compose_up() {
  local f="$1"
  run_write "重建/启动容器 ($f)" docker compose -f "$f" up -d
}

# ===========================================================================
# 阶段 7: 收尾提示
# ===========================================================================
stage_finish() {
  local ip; ip="$(hostname -I 2>/dev/null | awk '{print $1}')"; ip="${ip:-<服务器IP>}"
  if [ "$IS_FRESH_INSTALL" = "1" ]; then
    step "阶段 7 / 完成 · 剩下 3 步手动操作"
  else
    step "阶段 7 / 完成 · 体检/更新"
  fi
  if [ "$IS_FRESH_INSTALL" = "1" ]; then
  cat <<EOF

${C_G}${C_BOLD}后端已就绪！接下来在浏览器里完成最后 3 步:${C_RESET}

  ${C_BOLD}① 扫码登录机器人 QQ${C_RESET} — 打开 NapCat WebUI:  ${C_C}http://${ip}:6099${C_RESET}
       ${C_Y}登录要 token(WebUI 密钥)，两种查法任选:${C_RESET}
         · ${C_BOLD}文件${C_RESET}(推荐): 1Panel 文件管理器打开
             ${C_C}${ASTRBOT_DIR}/napcat/config/webui.json${C_RESET}
             里 ${C_BOLD}"token"${C_RESET} 引号内的值就是登录密钥
         · ${C_BOLD}日志${C_RESET}: ${C_C}docker logs napcat 2>&1 | grep -i token${C_RESET}
       进去后用${C_BOLD}手机 QQ 扫码${C_RESET}登录机器人号(${C_BOLD}建议小号${C_RESET}，主号易风控)。

  ${C_BOLD}② 接上 AstrBot${C_RESET} — ${C_Y}反向 WebSocket 需手动配两端(脚本不自动配)${C_RESET}:
       · AstrBot 后台 ${C_C}http://${ip}:6185${C_RESET}「平台适配器」加 ${C_BOLD}aiocqhttp${C_RESET},
         用${C_BOLD}反向 WS${C_RESET}、监听端口 ${C_BOLD}6199${C_RESET}
       · NapCat WebUI「网络配置」加 ${C_BOLD}WebSocket 客户端${C_RESET} ${C_C}ws://astrbot:6199/ws${C_RESET},
         消息格式选 ${C_BOLD}array${C_RESET}
       (详细图文见 docs/DEPLOY.md 第 6.2 节)

  ${C_BOLD}③ 确认管理员 QQ${C_RESET} — ${C_Y}${C_BOLD}必须填！否则公告/踢/封/关服/自检等管理指令没人能用！${C_RESET}
       插件配置 ${C_C}admin_qq${C_RESET} 要有你的 QQ 号(纯数字):
       ${C_C}${PLUGIN_CONFIG}${C_RESET}

${C_G}${C_BOLD}关于出图(t2i 文转图渲染):${C_RESET}
  本地渲染服务 ${C_C}astrbot-t2i${C_RESET} 已随 compose 一并部署(容器内地址 ${C_C}${T2I_ENDPOINT}${C_RESET}),
  用它出图比公共端点快且稳(不再走又慢又常 502 的官方公共端点)。
  ${C_BOLD}若脚本提示 cmd_config.json 尚未生成(全新安装首启前):${C_RESET}
  请进 AstrBot WebUI → ${C_BOLD}配置 → 其它 → 文转图${C_RESET}, 把
    · 策略(t2i_strategy) 设为 ${C_BOLD}remote${C_RESET}
    · 端点(t2i_endpoint) 设为 ${C_C}${T2I_ENDPOINT}${C_RESET}
  保存后重启 AstrBot 生效。(脚本能改到配置文件时已自动帮你设好, 无需再动。)

${C_G}全部完成后, 在 QQ 群里发一条:${C_RESET}  ${C_BOLD}/帕鲁自检${C_RESET}
可一键体检所有连接是否正常。

EOF
  else
  cat <<EOF

${C_G}${C_BOLD}已有部署，本次为体检/更新。${C_RESET}

    · 若插件有更新：到 AstrBot WebUI「插件管理 → 重载插件」使新代码生效
      (重载即可，通常无需重启容器)。
    · 配置已按需体检补齐；如本次改动过 compose，相关容器已重建。
    · 想连各镜像一起更新到最新：用 ${C_BOLD}--update${C_RESET} 模式重跑脚本。

${C_G}完成后在 QQ 群发一条${C_RESET} ${C_BOLD}/帕鲁自检${C_RESET} ${C_G}体检环境。${C_RESET}

EOF
  fi
  if is_dry; then
    warn "以上为演练结果。真正执行请去掉 --dry-run 重跑。"
  fi
}

# ===========================================================================
# main
# ===========================================================================
usage() {
  cat <<EOF
帕鲁服务器管家 · 一键安装脚本

用法:
  bash install.sh              真正执行(会在关键处停下问你 y/N)
  bash install.sh --dry-run    演练模式: 只检测/只显示 diff, 绝不改动
  DRY_RUN=1 bash install.sh    同上
  bash install.sh --update    更新模式: 拉取最新插件与各镜像并重建(不改配置)

选项:
  --dry-run    演练模式
  --update     更新模式(可与 --dry-run 叠加演练)
  -h, --help   显示本帮助
EOF
}

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --dry-run) DRY_RUN=1 ;;
      --update) UPDATE_MODE=1 ;;
      -h|--help) usage; exit 0 ;;
      *) err "未知参数: $1"; usage; exit 2 ;;
    esac
    shift
  done

  printf '%s\n' "${C_BOLD}${C_C}帕鲁服务器管家 · 一键安装${C_RESET}"

  if [ "$UPDATE_MODE" = "1" ]; then
    stage_precheck
    stage_update
    ok "脚本结束。"
    exit 0
  fi

  stage_precheck
  stage_deps
  stage_docker
  stage_1panel
  stage_astrbot
  stage_palworld
  stage_plugin
  stage_finish
  ok "脚本结束。"
}

if [ "${PALWORLD_INSTALL_SOURCE_ONLY:-0}" != "1" ]; then
  main "$@"
fi
