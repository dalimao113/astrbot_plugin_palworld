# 字体资产

## fusion-pixel-12px-proportional-zh_hans.subset.woff2

- 来源:[Fusion Pixel Font 缝合像素字体](https://github.com/TakWolf/fusion-pixel-font) 12px 比例版 zh_hans
- 许可:SIL Open Font License 1.1(见同目录 `OFL.txt`),允许自由嵌入 / 子集化 / 再分发
- 用途:pixel 主题(`card_style=pixel`)的中文像素字体,base64 内联进卡片 CSS,**不依赖任何 CDN / 外部网络**
- 子集化:仅保留 GB2312 常用汉字 + 项目实际用字 + ASCII/常用标点(约 7000 字形),原字体 6.7MB → 子集 woff2 约 244KB
- 更新方式:下载官方 12px-proportional-ttf 的 `zh_hans.ttf`,用 fonttools `pyftsubset --flavor=woff2` 按上述字符集重新子集化即可

> 原 pixel 主题曾用 Zpix 字体(付费、禁止子集化/再分发),为开源合规已替换为本 OFL 字体。
