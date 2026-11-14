# Jetson setup (overhead vision)

The Jetson Orin Nano runs `jetson/main.py`: overhead camera → detector → tracker → `vision.state` on the hub,
plus `/snapshot.jpg` for Gemini.

## 1. Base system

| | |
|---|---|
| Board | Jetson Orin Nano (8 GB) developer kit |
| JetPack | **6.x** (L4T R36.x, Ubuntu 22.04, Python 3.10, CUDA 12, TensorRT 8.6/10) |
| Power mode | `sudo nvpmodel -m 0 && sudo jetson_clocks` (max performance, run after every boot) |

Check the versions with `cat /etc/nv_tegra_release` and `python3 -c "import tensorrt; print(tensorrt.__version__)"`.

## 2. Connecting from the laptop (USB-C)

With the Jetson's USB-C port plugged into the laptop, L4T brings up a USB network link:

| Side | Address |
|---|---|
| Jetson | `192.168.55.1` |
| Laptop | `192.168.55.100` (this is what `jetson/main.py` uses for the hub by default) |

```bash
ssh <user>@192.168.55.1
```

If no new network interface shows up on the laptop: use the USB-C port next to the barrel jack (not a USB-A
port), use a data cable rather than a charge-only one, and wait about a minute after power-on. A serial console also
shows up as `/dev/cu.usbmodem*` on macOS (`screen /dev/cu.usbmodem* 115200`).

## 3. Python packages

Use the **system** `python3` so the JetPack TensorRT and CUDA bindings are visible:

```bash
sudo apt install -y python3-pip v4l-utils
# PyTorch + torchvision built for JetPack 6 (NVIDIA's wheels; pick the ones matching your JetPack)
#   https://docs.nvidia.com/deeplearning/frameworks/install-pytorch-jetson-platform/
pip3 install ultralytics websockets numpy
pip3 install "opencv-contrib-python<4.11"   # only if the system OpenCV lacks cv2.aruco
```

Ultralytics may install a CPU-only `torch` from PyPI over NVIDIA's wheel. If
`python3 -c "import torch; print(torch.cuda.is_available())"` prints `False`, reinstall NVIDIA's wheel.

Clone the repo on the Jetson (the vision code imports `server/common/` for config and the hub client).

## 4. Camera permissions

```bash
sudo usermod -aG video $USER      # then log out and back in
v4l2-ctl --list-devices           # find the overhead camera, usually /dev/video0
v4l2-ctl -d /dev/video0 --list-formats-ext   # it should offer MJPG 1280x720 @ 30
python3 -m jetson.camera --index 0           # prints the live fps (target: >= 15)
```

Exposure is set to manual by `jetson/camera.py`. If the image is too dark or too bright, set `CAMERA_EXPOSURE`
via `GENRATOR_CAMERA_EXPOSURE` or pass `exposure=` to `Camera`. V4L2 units are camera-specific; try 100–300.

## 5. Calibrate the table

```bash
python3 -m jetson.calibrate_tool            # click TL, TR, BR, BL, press s
python3 -m jetson.calibrate_tool --aruco    # or: ArUco 4x4 ids 0-3 taped at the corners
```

This writes `jetson/calibration.json`. Do it again whenever the camera or the table moves.

## 6. TensorRT engine

```bash
scripts/jetson_export.sh yolo11n 640       # writes jetson/models/yolo11n.engine (FP16)
```

`jetson/detector.py` loads `jetson/models/yolo11n.engine` automatically when it exists, and
`jetson/models/yolo11n.pt` (or downloads it) otherwise. Export the engine on the Jetson itself, because engines don't
transfer between devices or TensorRT versions.

## 7. Measured FPS

Run on the Jetson with the camera over the real table:

```bash
python3 scripts/jetson_bench.py --sizes 640 960
```

| Model | Input | FPS (detect+track) | p50 ms | p95 ms |
|---|---|---|---|---|
| yolo11n.pt (PyTorch) | 640 | _not measured yet_ | | |
| yolo11n.pt (PyTorch) | 960 | _not measured yet_ | | |
| yolo11n.engine (TensorRT FP16) | 640 | _not measured yet_ | | |
| yolo11n.engine (TensorRT FP16) | 960 | _not measured yet_ | | |

**Chosen input size: 640** (default in `jetson/detector.py` and `jetson/main.py --imgsz`). Switch to 960 only if
small items such as crisp packets and cables are missed and the engine still runs at ≥ 15 fps.

> TODO: replace the rows above with the bench output from the demo Jetson, and confirm or change the chosen size.

## 8. Run

```bash
python3 -m jetson.main                                   # hub at ws://192.168.55.100:8765/hub
python3 -m jetson.main --hub ws://<laptop-ip>:8765/hub   # over Wi-Fi instead
```

Check on the laptop that the status page (T97) shows `vision.state` arriving at about 10 Hz and `system.health` from
`vision`.

## 9. Start on boot (systemd)

`/etc/systemd/system/genrator-vision.service`:

```ini
[Unit]
Description=Genrator overhead vision
After=network-online.target
Wants=network-online.target

[Service]
User=<user>
WorkingDirectory=/home/<user>/sonar-bot-tune
ExecStartPre=/usr/bin/sudo /usr/bin/jetson_clocks
ExecStart=/usr/bin/python3 -m jetson.main
Restart=always
RestartSec=2
Environment=GENRATOR_LOG_LEVEL=INFO

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload && sudo systemctl enable --now genrator-vision
journalctl -u genrator-vision -f
```

(`ExecStartPre` with sudo needs a sudoers rule for `jetson_clocks`. Otherwise drop that line and run `jetson_clocks`
from `/etc/rc.local`.)
