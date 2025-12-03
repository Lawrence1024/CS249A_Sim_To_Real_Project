### Prerequisit
```
sudo apt update
sudo apt install cmake gcc-arm-none-eabi build-essential git python3
```

### Download Pico SDK as submodule and update the tiny usb module (inside pololu-3pi-2040)
```
git submodule add https://github.com/raspberrypi/pico-sdk.git
git submodule add https://github.com/pololu/pololu-3pi-2040-robot.git
git -C pico-sdk submodule update --init lib/tinyusb
```

### Install Picotool, in other location
```
sudo apt update
sudo apt install build-essential pkg-config libusb-1.0-0-dev cmake git

git clone https://github.com/raspberrypi/picotool.git
cd picotool

mkdir build
cd build
cmake .. -DPICO_SDK_PATH=<path-to-your-pico-sdk>
make -j$(nproc)

```

### Build (inside pololu-3pi-2040)
```
mkdir build
cd build
cmake ..
cmake --build .
```


### Upload 
```
picotool load -x <executable_name>.uf2
```