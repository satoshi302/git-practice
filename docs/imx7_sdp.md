# NXP i.MX7 Serial Download Protocol (SDP)

## 概要

i.MX7 SoCのROMブートローダーは、eMMCから有効なブートイメージを見つけられない場合に
SDPモード（USB HID経由のダウンロードモード）へ自動遷移します。

- USB VID: `0x15A2`
- USB PID: `0x0076` (i.MX7) / `0x007D` (i.MX6SL)
- インターフェース: USB HID (Class 0x03)

---

## プロトコル仕様

### HIDレポート構造

| Report ID | 方向 | サイズ | 用途 |
|-----------|------|--------|------|
| 1 | ホスト→デバイス | 17バイト | SDPコマンド送信 |
| 2 | ホスト→デバイス | 1025バイト | データ転送 |
| 3 | デバイス→ホスト | 5バイト | HABステータス応答 |
| 4 | デバイス→ホスト | 5バイト | DCD ACK/NACK |

### SDPコマンド構造 (16バイト, ビッグエンディアン)

```
[2B] CommandType
[4B] Address
[1B] Format (0x08=8bit / 0x10=16bit / 0x20=32bit)
[4B] DataCount
[4B] Data
[1B] Reserved
```

### コマンドタイプ一覧

| 値 | コマンド | 説明 |
|----|----------|------|
| 0x0101 | READ_REGISTER | レジスター読み取り |
| 0x0202 | WRITE_REGISTER | レジスター書き込み |
| 0x0404 | WRITE_FILE | バイナリをRAMへロード |
| 0x0505 | ERROR_STATUS | HABステータス取得 |
| 0x0A0A | DCD_WRITE | Device Configuration Data書き込み |
| 0x0B0B | JUMP_ADDRESS | アドレスへジャンプ・実行 |
| 0x0C0C | SKIP_DCD_HEADER | DCDヘッダースキップ |

---

## HAB (High Assurance Boot)

| ステータス値 | 意味 |
|-------------|------|
| `0x56787856` | HAB OPEN: 署名なしイメージ実行可 |
| `0x12343412` | HAB CLOSED: 署名付きイメージのみ実行可 |

**製品版PW4はHAB CLOSEDです。** SDP経由でコードを実行するには
Amazonが署名したU-Boot SPLが必要です。

GPL公開ソースからビルドした場合はAmazon秘密鍵での署名ができないため、
HAB CLOSEDデバイスでは直接コード実行はできません。
ただし、eMMCに有効なSPLが残っていれば通常起動できます。

---

## メモリマップ

| アドレス | 領域 | サイズ |
|----------|------|--------|
| `0x00910000` | OCRAM (オンチップRAM) | 256KB |
| `0x80000000` | DDR (DDRCInit後) | デバイスにより異なる |

OCRAM: DDR初期化前でも使用可能。SPLのロード先として使用。  
DDR: `0x80000000`以降はDCDによるDDRコントローラー初期化後に使用可能。

---

## 実装例 (Python)

```python
from kindle_recovery.level1_usb.sdp import recover_via_sdp

# SDP経由でU-Boot SPLをロードして実行
recover_via_sdp("uboot-spl.bin", load_addr=0x00910000)
```

---

## U-Boot SPLのビルド

AmazonはGPLに従いKindleのU-Bootソースを公開しています。

```bash
# Amazon GPLページからソースを取得
# https://www.amazon.com/gp/help/customer/display.html?nodeId=200203720

make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf- kindle_pw4_defconfig
make ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-

# 生成物: spl/u-boot-spl.bin
```

ビルドされたSPLはHAB署名なしのため、HAB CLOSEDデバイスでは実行できません。
HAB OPENデバイス（工場出荷前のサンプル等）でのみ有効です。
