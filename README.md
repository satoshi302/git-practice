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

## セットアップ

```bash
# システム依存パッケージ
sudo apt install libhidapi-libusb0 python3-pip

# udevルール設定 (sudo不要でUSBアクセス)
sudo bash scripts/setup_udev.sh

# Pythonパッケージ
pip install -r requirements.txt
```

## 使い方

```bash
# ガイド付き全自動ウィザード
python scripts/recover.py full

# USBモード確認
python scripts/recover.py detect

# 起動ログキャプチャ・診断 (UART)
python scripts/recover.py bootlog --port /dev/ttyUSB0

# U-Bootコンソール (UART)
python scripts/recover.py uboot --port /dev/ttyUSB0
```

## ドキュメント

- [ハードウェアガイド (UART配線・開け方)](docs/pw4_hardware.md)
- [i.MX7 SDPプロトコル](docs/imx7_sdp.md)
- [復旧判断フローチャート](docs/recovery_flowchart.md)
