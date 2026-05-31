# Kindle Paperwhite 4 Recovery Toolkit

エンジニアリング的アプローチによるKindle Paperwhite 4 (PW4) リカバリーツールキット。
完全放電・文鎮化したデバイスを3段階のエスカレーション戦略で復旧します。

## 対象デバイス

- Kindle Paperwhite 4 (第10世代, 2018〜2021年, Micro USB)
- SoC: NXP i.MX7D

## リカバリー戦略

| レベル | 方法 | リスク | 必要なもの |
|--------|------|--------|------------|
| Level 1 | USB Software (SDP) | 低 | USBケーブルのみ |
| Level 2 | UART Serial Access | 中 | USB-UARTアダプター + はんだ付け |
| Level 3 | eMMC Full Flash | 高 | Level 2 + ファームウェアイメージ |

## 動作環境

| OS | サポート | Python |
|----|----------|--------|
| macOS 12以上 | ✅ | 3.10以上 |
| Linux (Ubuntu/Debian) | ✅ | 3.10以上 |
| Windows 10/11 | ✅ | 3.10以上 |

## セットアップ

### Windows

```powershell
# PowerShellで実行 (管理者権限推奨)
.\scripts\setup_windows.ps1
```

> **注意**: pyusbでUSBデバイスにアクセスするには [Zadig](https://zadig.akeo.ie/) で WinUSB ドライバーのインストールが必要です。詳細はスクリプト実行後の案内を参照。

### macOS

```bash
bash scripts/setup_udev.sh
```

### Linux

```bash
sudo bash scripts/setup_udev.sh
```

## 使い方

```bash
# ガイド付き全自動ウィザード
python scripts/recover.py full

# USBモード確認
python scripts/recover.py detect

# 起動ログキャプチャ・診断 (UART) — ポートは自動検出
python scripts/recover.py bootlog

# ポートを明示する場合
python scripts/recover.py bootlog --port COM3        # Windows
python scripts/recover.py bootlog --port /dev/cu.usbserial-0001  # macOS
```

### シリアルポートの確認方法

**Windows**: デバイスマネージャー → ポート (COM と LPT)

```powershell
# PowerShellでも確認可能
.\scripts\detect_kindle.ps1
```

**macOS**:
```bash
ls /dev/cu.*
# 例: /dev/cu.usbserial-1410  /dev/cu.SLAB_USBtoUART
```

## ドキュメント

- [ハードウェアガイド (UART配線・開け方)](docs/pw4_hardware.md)
- [i.MX7 SDPプロトコル](docs/imx7_sdp.md)
- [復旧判断フローチャート](docs/recovery_flowchart.md)
