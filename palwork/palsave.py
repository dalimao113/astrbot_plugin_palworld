#!/usr/bin/env python3
"""解析 Palworld 服务器存档(PlM=Oodle压缩的GVAS)。复用 liboo2core.so。"""
import ctypes, struct
from palworld_save_tools.gvas import GvasFile
from palworld_save_tools.paltypes import PALWORLD_CUSTOM_PROPERTIES, PALWORLD_TYPE_HINTS

# 1.0 存档兼容：worldSaveData 顶层新增 InLockerCharacterInstanceIDArray(SetProperty)，
# 锁定的 save-tools 0.24.0 不识别 SetProperty，解析顶层属性即抛 "Unknown type: SetProperty"，
# 导致整份存档读不了、玩家信息全查不到。该数据档案提取用不到，注册跳过器：读掉 inner 类型名
# 与可选 GUID 后，用 size(payload 字节数)整块跳过，对齐到下一个属性即可。
from palworld_save_tools import archive as _archive
if not getattr(_archive.FArchiveReader, "_pal_setprop_patched", False):
    _orig_ar_property = _archive.FArchiveReader.property

    def _ar_property_with_set(self, type_name, size, path, nested_caller_path=""):
        if type_name == "SetProperty":
            array_type = self.fstring()
            id_ = self.optional_guid()
            self.skip(size)   # size = set body 字节数(NumRemoved+Num+元素)
            return {"array_type": array_type, "id": id_, "value": None, "skipped_set": True}
        return _orig_ar_property(self, type_name, size, path, nested_caller_path)

    _archive.FArchiveReader.property = _ar_property_with_set
    _archive.FArchiveReader._pal_setprop_patched = True

# 本服游戏版本的角色 blob 尾部有额外字节，0.24.0 解析器会报 "EOF not reached"。
# object(全部真实数据) 已在前面读完，这里宽容吞掉尾部不报错。
import palworld_save_tools.rawdata.character as _char
def _lenient_decode_bytes(parent_reader, char_bytes):
    reader = parent_reader.internal_copy(bytes(char_bytes), debug=False)
    data = {"object": reader.properties_until_end()}
    try:
        data["unknown_bytes"] = reader.byte_list(4)
        data["group_id"] = reader.guid()
    except Exception:
        pass
    return data
_char.decode_bytes = _lenient_decode_bytes

# 帕鲁容器槽位(队伍/帕鲁箱)：取 player_uid/instance_id/tribe，尾部多余字节吞掉。
import palworld_save_tools.rawdata.character_container as _cc
def _lenient_cc_decode(parent_reader, c_bytes):
    if len(c_bytes) == 0:
        return None
    reader = parent_reader.internal_copy(bytes(c_bytes), debug=False)
    data = {"player_uid": reader.guid(), "instance_id": reader.guid()}
    try:
        data["permission_tribe_id"] = reader.byte()
    except Exception:
        pass
    return data
_cc.decode_bytes = _lenient_cc_decode

import os as _os
_oo = ctypes.CDLL(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "liboo2core.so"))
_oo.OodleLZ_Decompress.restype = ctypes.c_int64
_oo.OodleLZ_Decompress.argtypes = [ctypes.c_char_p, ctypes.c_int64, ctypes.c_char_p, ctypes.c_int64,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int]

# 解压尺寸上限(防解压炸弹/DoS): 头部声明的 ulen/clen 均取自不可信文件, 超过即拒绝。
_MAX_SAV = 512 * 1024 * 1024   # 512 MiB

def _oodle(src, dstlen):
    if dstlen > _MAX_SAV:
        raise Exception(f"Oodle 解压尺寸 {dstlen} 超过上限 {_MAX_SAV}")
    dst = ctypes.create_string_buffer(dstlen)
    n = _oo.OodleLZ_Decompress(src, len(src), dst, dstlen, 0, 0, 0, None, None, None, None, None, None, 3)
    # 必须完整解压到声明长度: n<=0 是失败, 0<n<dstlen 是部分解压(截断), 都拒绝。
    if n != dstlen:
        raise Exception(f"Oodle decompress failed (n={n}, 期望 {dstlen})")
    return dst.raw[:dstlen]

def decompress_sav(data: bytes) -> bytes:
    """返回未压缩 GVAS 字节。支持 PlZ(zlib) / PlM(oodle)。"""
    if len(data) < 12:
        raise Exception(f"存档过短({len(data)} 字节), 缺少压缩头")
    ulen = struct.unpack('<I', data[0:4])[0]
    clen = struct.unpack('<I', data[4:8])[0]
    if ulen > _MAX_SAV or clen > _MAX_SAV:
        raise Exception(f"存档头声明尺寸超上限(ulen={ulen}, clen={clen}, max={_MAX_SAV})")
    magic = data[8:11]
    save_type = data[11]
    payload = data[12:]
    if magic == b'PlM':              # Oodle 压缩(本服)
        return _oodle(payload, ulen)
    if magic == b'PlZ':              # 官方 zlib
        import zlib
        # 带 max_length 的增量解压: 若还有 unconsumed_tail 说明输出会超上限(解压炸弹), 拒绝。
        def _zdec(buf):
            d = zlib.decompressobj()
            res = d.decompress(buf, _MAX_SAV)
            if d.unconsumed_tail:
                raise Exception("zlib 解压超过上限, 疑似解压炸弹")
            return res + d.flush()
        out = _zdec(payload)
        if save_type == 0x32:
            out = _zdec(out)
        return out
    raise Exception(f"未知存档魔数 {magic!r}")

# 只保留个人档案需要的自定义解码器；建筑/植被/基地等大块不解析(走默认原始字节)，
# 既避开它们的版本不兼容报错，又大幅提速。
_KEEP = {
    # GroupSaveDataMap(工会)本版本格式也变了，暂丢弃(工会名是可选项)，走默认原始字节
    ".worldSaveData.CharacterSaveParameterMap.Value.RawData",
    ".worldSaveData.ItemContainerSaveData.Value.RawData",
    # 物品槽 RawData 只是权限元数据(且本版本格式变了)，丢弃；ItemId/StackCount 走默认解析仍在
    ".worldSaveData.CharacterContainerSaveData.Value.Slots.Slots.RawData",
}
_CUSTOM = {k: v for k, v in PALWORLD_CUSTOM_PROPERTIES.items() if k in _KEEP}

import io as _io, contextlib as _ctx
def load_sav(path: str, full: bool = False) -> dict:
    with open(path, 'rb') as _f:
        raw = decompress_sav(_f.read())
    cp = PALWORLD_CUSTOM_PROPERTIES if full else _CUSTOM
    # save-tools 对未知结构会 print("Struct type for ... not found")，吞掉避免刷屏
    with _ctx.redirect_stdout(_io.StringIO()):
        g = GvasFile.read(raw, PALWORLD_TYPE_HINTS, cp)
    return g.dump()

if __name__ == '__main__':
    import sys, json
    j = load_sav('/tmp/palsave/Level.sav')
    wsd = j['properties']['worldSaveData']['value']
    print('worldSaveData keys:', list(wsd.keys()))
    cm = wsd['CharacterSaveParameterMap']['value']
    print('CharacterSaveParameterMap entries:', len(cm))
    # 分出玩家
    players = []
    pals = 0
    for e in cm:
        sp = e['value']['RawData']['value']['object']['SaveParameter']['value']
        if sp.get('IsPlayer', {}).get('value'):
            players.append((e['key'], sp))
        else:
            pals += 1
    print('players:', len(players), '| pals:', pals)
    for key, sp in players:
        uid = key['PlayerUId']['value']
        iid = key['InstanceId']['value']
        nick = sp.get('NickName', {}).get('value')
        lvl = sp.get('Level', {}).get('value')
        exp = sp.get('Exp', {}).get('value')
        print(f"  玩家 uid={uid} iid={iid} 昵称={nick} Lv={lvl} Exp={exp}")


# ============ 高层提取：每个玩家的档案(等级/技术点/背包/队伍) ============
import struct as _struct, glob as _glob, os as _os
def _vv(d):
    while isinstance(d, dict) and 'value' in d:
        d = d['value']
    return d
def _arr(d):
    """取 {value:{values:[...]}} 里的列表。"""
    d = d.get('value') if isinstance(d, dict) else None
    if isinstance(d, dict):
        d = d.get('values')
    return d if isinstance(d, list) else []
def _parse_item_slot(vals):
    """物品槽 RawData 字节 -> (item_id, count) 或 None。格式: [?int32][count int32][FString itemid]"""
    b = bytes(x & 0xff for x in vals)
    if len(b) < 12:
        return None
    for off in range(4, min(len(b) - 4, 20), 4):
        slen = _struct.unpack_from('<i', b, off)[0]
        if 2 <= slen <= 64 and off + 4 + slen <= len(b):
            try:
                s = b[off + 4:off + 4 + slen - 1].decode('ascii')
            except Exception:
                continue
            # 物品id须是合法标识(≥2字符,字母数字+下划线/连字符);否则是把count等字段误读为
            # slen的假匹配(如count=2被当成slen=2,读出单字节'#'),跳过继续找真正的 FString。
            if len(s) >= 2 and s != 'None' and s.replace('_', '').replace('-', '').isalnum():
                cnt = _struct.unpack_from('<i', b, off - 4)[0]
                return s, (cnt if cnt > 0 else 1)
    return None
def _fixed64(d):
    """FixedPoint64 (Hp/ShieldHP) -> 实际值(存档里是 ×1000)。"""
    inner = _vv(_vv(d).get('Value', {})) if isinstance(_vv(d), dict) else None
    return int(inner / 1000) if isinstance(inner, (int, float)) else 0
def _status_points(sp, field):
    """GotStatusPointList/GotExStatusPointList -> {状态名(日文内部): 点数}。"""
    out = {}
    for entry in _arr(sp.get(field, {})):
        if isinstance(entry, dict):
            nm = _vv(entry.get('StatusName', {}))
            if nm is not None:
                out[str(nm)] = _vv(entry.get('StatusPoint', {})) or 0
    return out
def _pal_brief(sp, iid='', shared=False):
    cid = _vv(sp.get('CharacterID', {}))
    boss = isinstance(cid, str) and cid.upper().startswith('BOSS_')
    if boss:
        cid = cid[5:]
    g = str(_vv(sp.get('Gender', {})) or '')
    phys = str(_vv(_vv(sp.get('PhysicalHealth', {}))) or '').split('::')[-1]   # 健康状态(濒死/重伤..)，双层EnumProperty，健康时缺省
    return {
        'char_id': cid, 'is_alpha': boss,
        'iid': str(iid or ''),                           # instance_id：跨玩家聚合去重用(尤其据点共享帕鲁)
        'shared': bool(shared),                          # True=无主(据点公会共享)工作帕鲁，被复制进每个成员档案
        'health': phys,                                  # ''=健康 / Dying=濒死 / Severe=重伤 / Fracture=骨折 ..
        'stomach': round(_vv(sp.get('FullStomach', {})) or 0),   # 饱食度(真实值，据点断粮会归0；上限见 max_full_stomach)
        'sanity': round(_vv(sp.get('SanityValue', {})) if sp.get('SanityValue') is not None else 100),  # SAN理智(真实值，缺省=100健康)
        'hunger': str(_vv(_vv(sp.get('HungerType', {}))) or '').split('::')[-1],   # 饥饿枚举 Normal/Hungry/Starvation(据点帕鲁真实饥饿)
        'worker_sick': str(_vv(_vv(sp.get('WorkerSick', {}))) or '').split('::')[-1],  # 据点工作病 Sprain扭伤/Weakness虚弱/Depression..
        'current_work': str(_vv(_vv(sp.get('CurrentWorkSuitability', {}))) or '').split('::')[-1],  # 当前工作(空=待命)
        'level': _vv(sp.get('Level', {})) or 1,
        'exp': _vv(sp.get('Exp', {})) or 0,
        'rank': _vv(sp.get('Rank', {})) or 1,            # 浓缩等级 1~5
        'hp': _fixed64(sp.get('Hp', {})),                # 实际最大生命
        'iv_hp': _vv(sp.get('Talent_HP', {})) or 0,
        'iv_atk': _vv(sp.get('Talent_Shot', {})) or 0,
        'iv_def': _vv(sp.get('Talent_Defense', {})) or 0,
        'gender': 'female' if 'Female' in g else ('male' if 'Male' in g else ''),
        'lucky': bool(_vv(sp.get('IsRarePal', {})) or False),
        'nickname': _vv(sp.get('NickName', {})) or '',
        'equip_waza': [str(w).split('::')[-1] for w in _arr(sp.get('EquipWaza', {}))],
        'passives': [str(p) for p in _arr(sp.get('PassiveSkillList', {}))],
        'souls': _status_points(sp, 'GotStatusPointList'),   # 灵魄强化加点
    }
def extract_profiles(save_dir):
    """解析存档目录 -> {player_uid: {...档案...}}。save_dir 含 Level.sav 和 Players/*.sav。"""
    j = load_sav(_os.path.join(save_dir, 'Level.sav'))
    wsd = j['properties']['worldSaveData']['value']
    inst2pal, players = {}, {}
    # 空世界(还没人上线存档)时该键不存在,当作无玩家
    _csp = wsd.get('CharacterSaveParameterMap')
    for e in (_csp.get('value', []) if _csp else []):
        # 单条 entry 结构异常时只跳过该条, 不让整次解析失败(否则上层进负缓存, 全员查不到档)
        try:
            uid = str(_vv(e['key']['PlayerUId'])); iid = str(_vv(e['key']['InstanceId']))
            sp = e['value']['RawData']['value']['object']['SaveParameter']['value']
            if sp.get('IsPlayer') and _vv(sp['IsPlayer']):
                players[uid] = sp
            else:
                inst2pal[iid] = sp
        except Exception:
            continue
    char_cont, item_cont = {}, {}
    for c in wsd.get('CharacterContainerSaveData', {}).get('value', []):
        char_cont[str(_vv(c['key']['ID']))] = _vv(c['value'].get('Slots', {})) or {}
    for c in wsd.get('ItemContainerSaveData', {}).get('value', []):
        item_cont[str(_vv(c['key']['ID']))] = _vv(c['value'].get('Slots', {})) or {}
    def slots_of(cont):
        return cont.get('values', []) if isinstance(cont, dict) else []
    out = {}
    player_cont_ids = set()   # 玩家自己的 队伍+帕鲁箱 容器(其余容器=据点工作容器)
    for pf in _glob.glob(_os.path.join(save_dir, 'Players', '*.sav')):
        try:
            sd = load_sav(pf)['properties']['SaveData']['value']
        except Exception:
            continue
        uid = str(_vv(sd['PlayerUId'])); sp = players.get(uid, {})
        prof = {'uid': uid, 'nickname': _vv(sp.get('NickName', {})) or '',
                'level': _vv(sp.get('Level', {})) or 1, 'exp': _vv(sp.get('Exp', {})) or 0,
                'tech_points': _vv(sd.get('TechnologyPoint', {})) or 0,
                'recipes': len(_arr(sd.get('UnlockedRecipeTechnologyNames', {}))),
                'hp': _fixed64(sp.get('Hp', {})), 'shield': _fixed64(sp.get('ShieldHP', {})),
                'stomach': round(_vv(sp.get('FullStomach', {})) or 0),
                'status': _status_points(sp, 'GotStatusPointList'),
                'ex_status': _status_points(sp, 'GotExStatusPointList'),
                'inventory': [], 'party': [], 'palbox': [], 'basecamp': []}
        # 背包(各容器合并)
        inv = sd.get('InventoryInfo', {}).get('value', {})
        merged = {}
        for ref in inv.values():
            cid = str(_vv(_vv(ref).get('ID', {})))
            for s in slots_of(item_cont.get(cid, {})):
                rd = _vv(s.get('RawData', {})); vals = rd.get('values', []) if isinstance(rd, dict) else []
                r = _parse_item_slot(vals)
                if r:
                    merged[r[0]] = merged.get(r[0], 0) + r[1]
        prof['inventory'] = [{'id': k, 'count': v} for k, v in merged.items()]
        # 队伍(出战) / 帕鲁箱(全部)
        def _pals_in(container_ref, dst):
            cid = str(_vv((_vv(container_ref) or {}).get('ID', {})))
            player_cont_ids.add(cid)
            for s in slots_of(char_cont.get(cid, {})):
                iid = str((_vv(s.get('RawData', {})) or {}).get('instance_id', ''))
                pal = inst2pal.get(iid)
                if pal:
                    dst.append(_pal_brief(pal, iid))
        _pals_in(sd.get('OtomoCharacterContainerId', {}), prof['party'])
        _pals_in(sd.get('PalStorageContainerId', {}), prof['palbox'])
        out[uid] = prof
    # 据点工作帕鲁：在"非玩家队伍/帕鲁箱"的容器里(即据点工作容器)。
    # 有 OwnerPlayerUId 的归对应主人；据点是公会共享，工作帕鲁的 OwnerPlayerUId 常为空
    # (属于据点/公会而非个人)，这些收为 shared，最后分给所有玩家(公会成员都看得到)。
    shared_base = []
    for cid, slots in char_cont.items():
        if cid in player_cont_ids:
            continue
        for s in slots_of(slots):
            iid = str((_vv(s.get('RawData', {})) or {}).get('instance_id', ''))
            pal = inst2pal.get(iid)
            if not pal:
                continue
            owner = str(_vv(pal.get('OwnerPlayerUId', {})) or '')
            prof = out.get(owner) if owner else None
            if prof is not None:
                prof['basecamp'].append(_pal_brief(pal, iid))
            else:
                shared_base.append(_pal_brief(pal, iid, shared=True))   # 无主(据点公会共享)的工作帕鲁
    if shared_base:
        for prof in out.values():
            prof['basecamp'].extend(shared_base)
    return out


# ============ 公会(GroupSaveDataMap) 解析 ============
# 本版本 group RawData 字节格式变了(官方 group.py 在 base_camp_points 崩)。
# group_id(16)+group_name(fstring)+handles+org+base_camp 之后的"成员段"格式未变且在末尾，
# 用"解析到缓冲区末尾"验证法定位成员段(player_count + [uid16+last_i64+name_fstring]*N)，
# 跳过中段变了的字段。成员名/UID/最后在线 可靠解出；中段(基地点坐标)暂不取。
def _gstr(b, o):
    n = _struct.unpack_from('<i', b, o)[0]; o += 4
    if n == 0:
        return '', o
    if n < 0:
        return b[o:o - n * 2 - 2].decode('utf-16-le', 'ignore'), o - n * 2
    return b[o:o + n - 1].decode('utf-8', 'ignore'), o + n
import uuid as _uuid
def _guid_hex(b16):
    """GVAS 原始 GUID 字节(小端) -> 与 PlayerUId 一致的 canonical hex(大写)。"""
    try:
        return _uuid.UUID(bytes_le=bytes(b16)).hex.upper()
    except Exception:
        return bytes(b16).hex().upper()
def _parse_guild_bytes(b):
    """-> {members:[{name,uid,last_online}], admin_uid} 或 None。uid=与档案playerId一致的hex。"""
    off = 16
    _, off = _gstr(b, off)   # group_name(单人公会=玩家UID hex；多人=空，真名在中段)
    for start in range(off, len(b) - 8):
        o = start
        cnt = _struct.unpack_from('<i', b, o)[0]; o += 4
        if not (1 <= cnt <= 64):
            continue
        members = []; ok = True
        for _ in range(cnt):
            if o + 28 > len(b):
                ok = False; break
            uid = _guid_hex(b[o:o + 16]); o += 16
            last = _struct.unpack_from('<q', b, o)[0]; o += 8
            nlen = _struct.unpack_from('<i', b, o)[0]
            if not (-64 <= nlen <= 64) or nlen == 0:
                ok = False; break
            nm, o = _gstr(b, o)
            if not nm.strip():
                ok = False; break
            members.append({'name': nm, 'uid': uid, 'last_online': last})
        if ok and members and abs(o - len(b)) <= 6:
            admin = _guid_hex(b[start - 16:start]) if start >= 16 else ''
            return {'members': members, 'admin_uid': admin}
    return None
def extract_guilds(save_dir):
    """解析 Level.sav -> [{members:[{name,uid,last_online}], admin_uid}]，按成员数降序。"""
    j = load_sav(_os.path.join(save_dir, 'Level.sav'), full=False)
    gm = j['properties']['worldSaveData']['value'].get('GroupSaveDataMap', {}).get('value', [])
    guilds = []
    for e in gm:
        gt = str(_vv(e['value'].get('GroupType', {})) or '')
        if 'Guild' not in gt:
            continue
        rd = _vv(e['value'].get('RawData', {}))
        vals = rd.get('values') if isinstance(rd, dict) else None
        if not vals:
            continue
        b = bytes(x & 0xff for x in vals)
        try:
            g = _parse_guild_bytes(b)
        except Exception:
            g = None
        if g:
            guilds.append(g)
    guilds.sort(key=lambda x: len(x['members']), reverse=True)
    return guilds
