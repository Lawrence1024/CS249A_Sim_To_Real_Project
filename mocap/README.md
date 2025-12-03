
# Manually assign (Ethernet) IP address

### Ubuntu Example:
* Ethernet device: enp0s31f6
* Desried ethernet ip: 169.254.10.222
```
sudo ip addr add 169.254.10.222/24 dev enp0s31f6
sudo ip link set enp0s31f6 up
```