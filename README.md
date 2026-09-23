# LAN Observer

面向 6 英寸安卓手机的轻量局域网性能看板。一个容器同时提供网页、Beszel 数据代理、爱快路由器 SNMP 采集和设置页。

## 当前适配状态

- 已按现场 Beszel `0.13.2` 的 PocketBase API 字段实现，兼容 `systems.info` 中的新旧带宽字段。
- Beszel 地址预填为 `http://192.168.1.83:8090`；账号需在设置页填写。
- 爱快尚未就位，因此 SNMP 默认关闭。就位后在网页中填写地址、团体名并“发现接口”。
- 横屏和竖屏各有一套 JSON 模板。运行镜像不包含 React、Node 或可视化编辑器。

## 启动

```bash
cd /Users/cloudu/Hub/lan-observer
docker compose up -d --build
```

手机访问：`http://<Docker主机局域网IP>:18090`

设置页面：`http://<Docker主机局域网IP>:18090/settings`

首次进入设置无需 PIN。建议保存时设置至少 4 位管理 PIN。配置保存在 `./data/config.json`，该目录不会打入镜像。

## Beszel 设置

1. 建议在 Beszel 中新建只读用户供本项目使用。
2. 在设置页填写地址、邮箱和密码，先保存，再点“测试连接”。
3. 看板通过容器后端访问 Beszel，Beszel 密码不会返回手机浏览器。

Beszel agent 的常规状态数据本身约按分钟更新；页面与 WAN SNMP 数据流保持长连接，SNMP 可按 1–2 秒采样。若需要 Beszel 主机指标真正达到 1 秒粒度，需额外实现 PocketBase `rt_metrics` 实时订阅，本版本未伪称分钟数据为秒级数据。

## 爱快 SNMP 设置

在爱快管理界面启用 SNMP v2c，并把访问来源限制为运行本容器的主机 IP。设置页中填写：

- 路由器 LAN 地址和 UDP 161 端口；
- 单独生成的只读团体名；
- 保存后点击“发现接口”，选择实际 WAN 接口。

默认采用 IF-MIB 64 位计数器：

- 下载：`ifHCInOctets`，OID `1.3.6.1.2.1.31.1.1.1.6.{ifIndex}`
- 上传：`ifHCOutOctets`，OID `1.3.6.1.2.1.31.1.1.1.10.{ifIndex}`

如果爱快对 WAN 方向的定义与物理接口方向相反，可直接在高级设置中互换两个 OID。

## JSON 模板

内置模板位于：

- `templates/landscape.json`
- `templates/portrait.json`
- 规范：`templates/dashboard.schema.json`

设置页支持载入、编辑、导入和导出模板。模板保存在手机浏览器的 `localStorage`，因此界面调整不会增加镜像体积，也不会影响其他手机。

diagrams.net / draw.io 适合做布局草图，但其 XML 画布格式不适合作为运行时配置。本项目采用更稳定、可校验的 JSON Schema：在 draw.io 按 12 列（横屏）或 6 列（竖屏）画草图，再把组件的 `x/y/w/h` 填入 JSON 即可。可用的组件类型为 `wan`、`systems`、`status`、`clock`。

示例组件：

```json
{
  "id": "systems",
  "type": "systems",
  "title": "设备性能",
  "x": 1,
  "y": 4,
  "w": 12,
  "h": 7,
  "options": { "metrics": ["cpu", "memory", "disk", "temperature"] }
}
```

## 运维与安全边界

- 项目定位是可信局域网看板，不应直接映射到公网。
- HTTP 下管理 PIN 和数据未加密；跨不可信网络请在前面放置 HTTPS 反向代理。
- 配置文件权限设为 `0600`，但目前是明文持久化；保护好 `data` 卷和主机备份。
- 容器以非 root 用户运行、丢弃全部 Linux capabilities，并启用 `no-new-privileges`。

## 验证

```bash
python3 -m unittest discover -s tests -v
docker compose config
docker compose build
```

健康检查：`curl http://127.0.0.1:18090/api/health`
# phone-performance-monitor
