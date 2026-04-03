# web-FileCheck

`web-FileCheck` 是一個重新設計中的檔案比對 Web 工具，目標是取代舊的 BOM comparison 頁面，改成支援多種檔案格式的雙檔比對平台。

英文輔助說明：`web-FileCheck` is a multi-format file comparison web app for comparing two files and presenting readable differences.

## 專案目標

- 上傳兩個檔案進行比對
- 依檔案型態自動切換比對模式
- 支援表格型檔案與文件型檔案
- 保存上傳檔與比對結果
- 部署於 `10.10.10.30:4000`

## 目前已完成

目前版本已可正常啟動，且具備以下能力：

- 前端上傳頁面
- `GET /api/health`
- `GET /api/capabilities`
- `POST /api/compare-plan`
- `POST /api/compare`
- `GET /api/compare/:id`
- 真實 `multipart/form-data` 上傳處理
- 上傳檔存檔
- 比對結果存成 JSON

## 目前可用格式

### 文件型比對 Document Mode

已支援：

- `txt`
- `md`
- `docx`
- `pdf`（限可抽文字的 text-based PDF）

目前提供：

- paragraph-level diff
- section-level diff
- added / removed paragraphs
- changed sections

### 表格型比對 Spreadsheet Mode

已支援：

- `xls`
- `xlsx`

目前提供：

- row-level diff
- added / removed / changed rows
- duplicate key diagnostics
- missing key diagnostics

## 尚未完成

後續再評估：

- scanned PDF OCR
- legacy `.doc`
- 匯出報表強化
- 歷史記錄查詢頁

## 執行方式

### 本機開發 Local Run

```bash
cp .env.example .env
node src/server.js
```

預設開啟：

- `http://localhost:4000`

### Smoke Test

```bash
npm run test:smoke
```

這個測試目前會驗證：

- `md` 比對流程
- `xlsx` 比對流程
- `docx` 比對流程
- `pdf` 比對流程

## 部署資訊

目前目標部署主機：

- Host: `10.10.10.30`
- Port: `4000`

遠端程式位置：

- `/root/web-FileCheck`

遠端資料位置：

- `/data/web-FileCheck/uploads`
- `/data/web-FileCheck/results`
- `/data/web-FileCheck/reports`

目前服務名稱：

- `web-filecheck.service`

## 專案結構

```text
web-FileCheck/
├─ public/                 前端靜態頁面
├─ scripts/                本地 smoke test
├─ src/
│  ├─ comparers/           比對邏輯
│  ├─ parsers/             格式解析邏輯
│  ├─ utils/               HTTP / 檔案 / multipart 工具
│  ├─ config.js            基本設定
│  └─ server.js            HTTP 服務入口
├─ storage/                本地開發用資料夾
├─ package.json
└─ README.md
```

## API 摘要

- `GET /api/health`
  - 健康檢查
- `GET /api/capabilities`
  - 查看目前支援格式與儲存路徑
- `POST /api/compare-plan`
  - 先看兩個檔案名稱會落在哪種比對模式
- `POST /api/compare`
  - 實際上傳並執行比對
- `GET /api/compare/:id`
  - 讀取既有比對結果

## 開發備註

- 目前 `.env` 範例已提供，但遠端正式部署是用 `systemd` 環境變數啟動
- 本機 `storage/` 內容不會進 Git
- `xlsx` 套件目前有 1 個 high severity audit 提示，之後需要再評估升級或替代方案

## 相關文件

- 規格文件請看 [SPEC.md](/Z:/MyCoding/WinApp-AudioPlayer-Converter/web-FileCheck/SPEC.md)
