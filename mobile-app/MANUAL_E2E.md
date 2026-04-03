# Mobile App Manual E2E (M5-PR3)

This checklist verifies the minimum end-to-end path:
`start generation -> see progress -> open artifact entry -> preview -> submit publish -> check history/version`.

## 1. Build and install

```powershell
cd mobile-app
.\gradlew.bat :app:assembleDebug
```

Install `app-debug.apk` to an Android emulator/device.

## 2. Login and project selection

1. Open the app, enter username/password, tap `登录`.
2. Go to `我的` tab:
   - If testing online mode, set `控制面 Base URL` (example: `http://10.0.2.2:8080`) and save.
   - If Base URL is empty, the app runs in offline mock mode.
3. Go to `项目` tab and select a project (default `proj-1`).

## 3. Create task and observe progress

1. Go to `任务` tab.
2. Enter a natural language prompt and tap `发起任务`.
3. Open task detail and verify:
   - Progress bar updates.
   - Status transitions to `SUCCEEDED` (online polling or offline simulation).
   - `查看产物` button appears after success.

## 4. Artifact preview and publish entry

1. Tap `查看产物`, then open an artifact item.
2. On artifact detail page:
   - Tap `加载预览` and verify preview content or clear error prompt.
   - Fill `版本号` and tap `提交发布申请`.
3. Verify success hint appears on the page.

## 5. History and version verification

1. Go back to `产物` tab and tap `历史记录`.
2. Verify the new record exists with:
   - version label
   - task id
   - artifact name/id
   - status
   - formatted timestamp

If all checks pass, the M5-PR3 mobile flow is complete.
