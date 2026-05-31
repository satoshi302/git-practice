# 復旧判断フローチャート

## クイックスタート

まず `python scripts/recover.py detect` または `bash scripts/detect_kindle.sh` を実行してください。

---

## 判断フロー

```
KindleをUSBで接続
        │
        ▼
  lsusb / detect で確認
        │
  ┌─────┴──────┐
  │            │
見える         見えない
  │            │
  ▼            ▼
何のVID/PID?   充電待機 (20分)
  │            │
  │            ├─ それでも見えない →【UART接続へ】
  │            │
  │            └─ 見えた → フローに戻る
  │
  ├─ 0x1949/0x0004 (通常モード)
  │     → USBドライブとして認識
  │     → SSH: ssh root@192.168.2.2 (USBNet有効時)
  │     → OTAファイルをKindleのrootに置いて再起動
  │
  ├─ 0x1949/0x0005 (USBNetモード)
  │     → ping 192.168.2.2 で到達確認
  │     → SSH接続してコマンド実行
  │     → /mnt/us/update_*.bin を置いて reboot
  │
  ├─ 0x1949/0x0006 (CDCシリアル)
  │     → screen /dev/ttyACM0 115200
  │
  └─ 0x15A2/0x0076 or 0x007D (SDP ROMモード)
        → python scripts/recover.py sdp --binary uboot-spl.bin
        → ※HAB CLOSEDの場合は署名済みSPLが必要
        → SDP成功後: UARTでU-Bootをキャッチ → eMMCリフラッシュへ


【UART接続】
  USB-UARTアダプターをテストパッドに接続 (docs/pw4_hardware.md参照)
        │
        ▼
  python scripts/recover.py bootlog --port /dev/ttyUSB0
        │
  起動ログを解析
        │
  ┌─────┴────────────┐
  │                  │
U-Boot出力あり      出力なし
  │                  │
  ├─ autoboot割込可  │  → SoC電源断 / 配線ミス / eMMC完全破損
  │   ↓              │  → SDP USB経由で試みる
  │   uboot コマンド  │  → ハードウェア修理 (eMMC交換)
  │   でeMMCリフラッシュ
  │
  ├─ MMC error / no card
  │   → eMMCハードウェア障害
  │   → コネクター再接合 or BGA再はんだ
  │
  ├─ SPL checksum invalid
  │   → U-Boot SPL破損
  │   → SDP経由でRAMに直接ロード
  │
  └─ HAB Authentication Error
      → HAB署名検証失敗
      → 公式ファームウェアのみ使用可


【eMMCリフラッシュ (U-Boot経由)】

  U-Boot割り込み成功
        │
        ▼
  USBNet TFTP設定
  setenv ipaddr 192.168.2.2
  setenv serverip 192.168.2.1
        │
        ▼
  ホスト側でTFTPサーバー起動
  (atftpd or tftpd-hpa, ファイルをtftp rootに置く)
        │
        ▼
  U-Boot側でtftpboot + eMMC書き込み
  python scripts/recover.py flash os --image firmware/os.img --port /dev/ttyUSB0
        │
        ▼
  reset または bootm で再起動
```

---

## 必要なファームウェアの入手

| ファイル | 入手先 |
|----------|--------|
| 公式ファームウェア | Amazon OTA: `python scripts/recover.py` の `firmware` サブコマンド |
| U-Boot SPL (OPEN) | Amazon GPL公開ソース (`docs/imx7_sdp.md` 参照) |
| MfgTool bootstrap | NXP iMX Developer resources (登録必要) |

---

## トラブルシューティング

| 症状 | 対処 |
|------|------|
| USBに全く反応なし | ケーブル/アダプター変更, 30分以上充電 |
| UARTに全く出力なし | TX/RX配線逆確認, ボーレート確認 (115200), GND接続確認 |
| SDP接続できるがJUMP後に無反応 | HAB CLOSED: 署名済みSPL必要 |
| U-Boot割り込めない | Amazon独自キー: space/Enter/f を素早く連続入力 |
| TFTP失敗 | ホストのIPを192.168.2.1に設定, Firewall無効化 |
