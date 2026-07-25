# HA Sesame BLE

<p align="center">
  <img src="custom_components/sesame_ble/brand/icon.png" alt="HA Sesame BLE icon" width="180">
</p>

[![GitHub Release](https://img.shields.io/github/v/release/bingxyz/ha-sesame-ble?color=ff336c)](https://github.com/bingxyz/ha-sesame-ble/releases)
[![CI](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/ci.yml/badge.svg)](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/ci.yml)
[![Validate](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/validate.yml/badge.svg)](https://github.com/bingxyz/ha-sesame-ble/actions/workflows/validate.yml)
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5)](https://www.hacs.xyz/docs/faq/custom_repositories/)
[![License](https://img.shields.io/badge/license-MIT-29b6ff)](LICENSE)

[English](README.md) | [日本語](README.ja.md) | [繁體中文](README.zh-TW.md)

`ha-sesame-ble` 是直接從 Home Assistant 控制 CANDY HOUSE SESAME 智慧
門鎖的自訂整合，同時讓 ESP32 保持為標準、可替換的 Bluetooth Proxy——
ESP32 不需要任何 SESAME 專用 ESPHome component 或韌體。

即使只有一顆 ESP32，這個架構仍然有價值。SESAME 的驗證、加密、狀態及
命令邏輯由 Home Assistant 管理；ESP32 只提供通用 BLE 傳輸，也能繼續
服務其他 Bluetooth 裝置。

`0.1.x` 版**僅支援 SESAME 5 Pro**，可透過本機 Bluetooth adapter 或
ESPHome Bluetooth Proxy 連接。

> [!IMPORTANT]
> 第一版功能已完成並有自動化測試，也已透過 ESPHome Bluetooth Proxy
> 與實體 SESAME 5 Pro 驗證。Proxy 自動切換與長期運作穩定性仍需持續驗證。

## 支援型號

| 型號 | 狀態 |
| --- | --- |
| SESAME 5 Pro | 已支援並以實體硬體測試 |
| SESAME 5 | `0.1.x` 尚未啟用；底層函式庫支援，但本整合尚未驗證 |
| SESAME 5 US | `0.1.x` 尚未啟用；底層函式庫支援，但本整合尚未驗證 |
| SESAME 6 系列及其他所有 CANDY HOUSE 產品 | 不支援 |

本整合會刻意拒絕 SESAME 5 Pro 以外型號的 Bluetooth 探索結果。即使相關
型號共用 CANDY HOUSE Bluetooth service UUID，也不會出現在設定流程中。
每個型號都必須通過協定及實體硬體驗證後才會開放支援。

## 為什麼需要這個專案

核心目標是將 SESAME 專用邏輯保留在 Home Assistant，而不是把 ESP32
變成專用門鎖控制器：

- 使用一般 ESPHome Bluetooth Proxy，不需要自訂 component
- 更新、測試及除錯整合時，不需要重新編譯或刷寫 ESP32
- 將憑證、裝置狀態、自動化及備份還原流程集中在 Home Assistant
- 同一顆 ESP32 仍可服務其他 Bluetooth 裝置
- 更換 ESP32 時，不需要遷移 SESAME 專用韌體或邏輯

簡單來說，ESP32 是可替換的藍牙網路卡，而不是門鎖控制器。

Home Assistant 現有的 `sesame` 整合，是針對初代 SESAME Lock 及其 Wi-Fi
Access Point 的舊式雲端輪詢整合，不是 SESAME 5 Pro 的本地 BLE 整合。

第三方 `esphome-sesame3` 專案可以讓一顆 ESP32 直接控制 SESAME，但通訊
session 及門鎖專用邏輯也會由該 ESP32 持有。這種架構適合沒有 Home
Assistant，或控制邏輯必須獨立運行在微控制器上的情境；如果 Home Assistant
本來就是整套系統的中心，便不需要如此部署。

將通訊協定保留在 Home Assistant，也會帶來額外的多 Proxy 優勢：所有
Proxy 共用同一份整合狀態，斷線後 Home Assistant 可以重新選擇可達的
BLE 路徑。

```text
SESAME 5 Pro
    ↕ BLE
任何可連線的 ESPHome Bluetooth Proxy
    ↕ ESPHome API／網路
Home Assistant + ha-sesame-ble
```

ESPHome 端只需要標準的主動連線 Proxy：

```yaml
esp32_ble_tracker:

bluetooth_proxy:
  active: true
```

這份 YAML 只提供 BLE 傳輸。驗證、加密、狀態及門鎖命令則由本 Home
Assistant 整合使用 `gomalock` Python 函式庫實作。

## 第一版功能

- 自動探索 SESAME 5 Pro Bluetooth 裝置
- 透過 Home Assistant UI 設定
- 輸入 Owner／Manager 分享 URL 或 32 字元 Secret Key
- 明確的上鎖及解鎖操作
- 門鎖狀態、卡住狀態及可用性
- 角度、電量百分比、電池電壓及 Bluetooth 訊號強度感測器
- 上次 Home Assistant 操作結果及端到端耗時診斷
- 有上限的重連退避，並在斷線後重新選擇 Home Assistant BLE 路徑
- 隱去敏感資料的診斷資訊

## 實體

| 實體 | 預設 | 說明 |
| --- | --- | --- |
| 門鎖 | 啟用 | 上鎖／解鎖狀態及控制命令 |
| 角度 | 啟用 | 目前機械角度 |
| 電量 | 啟用 | 預估電量百分比 |
| 電池電壓 | 停用 | 門鎖回報的原始電壓 |
| 訊號強度 | 停用 | 最近一次可連線 BLE 廣播的 RSSI |
| 上次 HA 操作結果 | 停用 | 上次 HA 命令成功或失敗 |
| 上次 HA 操作耗時 | 停用 | 上次 HA 命令的端到端耗時 |
| 低電量 | 停用 | SESAME 的低電量旗標 |

狀態來自 SESAME 的機械狀態通知。如果門鎖角度不在校正過的上鎖或解鎖
範圍內，門鎖狀態會顯示未知，但角度感測器仍會回報位置。

訊號強度是 Home Assistant 或 ESPHome Bluetooth Proxy 最近收到的廣播
診斷資料，不是持續 GATT 連線中的即時量測值，因此門鎖保持連線時可能
長時間不變。

操作診斷只涵蓋由 Home Assistant 送出的命令。耗時包含必要的重連與登入
時間；成功代表 SESAME 已接受命令，機械操作失敗仍會由門鎖實體的卡住
狀態回報。

## 安裝

本 repository 可作為 HACS 自訂 repository 安裝：

1. 在 Home Assistant 開啟 **HACS**。
2. 開啟選單並選擇 **Custom repositories**。
3. 新增 `https://github.com/bingxyz/ha-sesame-ble`，類別選擇
   **Integration**。
4. 在 HACS 開啟 **Sesame BLE** 並選擇 **Download**。
5. 重新啟動 Home Assistant。
6. 確認可連線的 Bluetooth adapter 或 ESPHome Bluetooth Proxy 位於範圍內；
   Home Assistant 會自動探索支援的 SESAME 5 Pro。

HACS 會將整合安裝到 Home Assistant 設定目錄的 `custom_components/`
資料夾，未來版本也能從同一筆 HACS repository 安裝及更新。

`v0.1.0` manifest 會從維護中的
[`bingxyz/gomalock`](https://github.com/bingxyz/gomalock) fork，以不可變的
commit 安裝 `gomalock` 2.2.0。這個 fork 在原始
[`meronepy/gomalock`](https://github.com/meronepy/gomalock) 專案上加入
Home Assistant BLE 路由與斷線 hook。若這些 transport hook 未來被上游
接受，即可改回 PyPI release。

本機開發會直接使用相鄰的 `../gomalock` checkout：

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy custom_components
```

設定時只能提供以下其中一項：

- Owner／Manager 的 `ssm://` 分享 URL；或
- 門鎖的 32 字元十六進位 Secret Key。

儲存 config entry 前，整合會進行一次真正的加密 BLE 登入來驗證憑證。

## 專案界線

- `ha-sesame-ble` 是 Home Assistant 整合，也是本專案的主要維護成果。
- `gomalock` 仍是獨立的通訊協定函式庫；本 workspace 包含向下相容的
  Home Assistant 路由 transport 擴充。
- `esphome-sesame3` 與 `libsesame3bt` 是有用的參考資料，但不是此架構的
  runtime dependency。
- 第一版不包含 SESAME 歷史紀錄同步與舊型 SESAME OS2 產品支援。

完整分析、決策、風險與實作規劃請參考
[研究與設計](docs/research-and-design.md)（英文）。

## 參考資料

- [CANDY HOUSE API 文件](https://github.com/CANDY-HOUSE/API_document)
- [gomalock 上游專案](https://github.com/meronepy/gomalock)
- [gomalock HA transport fork](https://github.com/bingxyz/gomalock)
- [esphome-sesame3](https://github.com/homy-newfs8/esphome-sesame3)
- [Home Assistant Bluetooth 開發文件](https://developers.home-assistant.io/docs/bluetooth/)
- [Home Assistant Bluetooth API](https://developers.home-assistant.io/docs/core/bluetooth/api/)
- [現有 Home Assistant Sesame 整合](https://www.home-assistant.io/integrations/sesame/)
