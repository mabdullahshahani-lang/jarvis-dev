from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import screen_brightness_control as sbc

def _get_volume_interface():
    devices = AudioUtilities.GetSpeakers()
    try:
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    except AttributeError:
        # newer pycaw versions wrap the COM object differently
        interface = devices._dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))

def set_volume(percent):
    """percent: 0-100"""
    percent = max(0, min(100, percent))
    volume = _get_volume_interface()
    volume.SetMasterVolumeLevelScalar(percent / 100, None)

def get_volume():
    volume = _get_volume_interface()
    return round(volume.GetMasterVolumeLevelScalar() * 100)

def change_volume(delta):
    """delta: positive or negative number to add to current volume"""
    current = get_volume()
    set_volume(current + delta)
    return get_volume()

def mute():
    volume = _get_volume_interface()
    volume.SetMute(1, None)

def unmute():
    volume = _get_volume_interface()
    volume.SetMute(0, None)

def set_brightness(percent):
    percent = max(0, min(100, percent))
    sbc.set_brightness(percent)

def get_brightness():
    return sbc.get_brightness()[0]

def change_brightness(delta):
    current = get_brightness()
    new_val = max(0, min(100, current + delta))
    set_brightness(new_val)
    return new_val