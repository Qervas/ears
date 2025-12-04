"""Test all input devices to find one that captures system audio."""

import sounddevice as sd
import numpy as np
import time


def test_device(device_id: int, duration: float = 2.0) -> float:
    """Test a device and return max amplitude detected."""
    try:
        device_info = sd.query_devices(device_id)
        if device_info['max_input_channels'] < 1:
            return -1  # Not an input device

        sample_rate = int(device_info['default_samplerate'])

        # Record for a short duration
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            device=device_id,
            dtype=np.float32
        )
        sd.wait()

        max_amp = np.max(np.abs(recording))
        return max_amp
    except Exception as e:
        return -2  # Error


def main():
    print("=" * 60)
    print("TESTING ALL INPUT DEVICES - Keep your Swedish audio playing!")
    print("=" * 60)
    print()

    devices = sd.query_devices()
    results = []

    for i, dev in enumerate(devices):
        if dev['max_input_channels'] < 1:
            continue  # Skip output-only devices

        name = dev['name']
        print(f"Testing [{i}] {name[:45]}...", end=" ", flush=True)

        amp = test_device(i, duration=2.0)

        if amp == -1:
            print("SKIP (not input)")
        elif amp == -2:
            print("ERROR")
        elif amp < 0.001:
            print(f"SILENT (amp: {amp:.6f})")
        else:
            print(f"*** AUDIO DETECTED! *** (amp: {amp:.4f})")
            results.append((i, name, amp))

    print()
    print("=" * 60)
    print("RESULTS - Devices with audio detected:")
    print("=" * 60)

    if results:
        results.sort(key=lambda x: x[2], reverse=True)
        for device_id, name, amp in results:
            print(f"  [{device_id}] {name} (amplitude: {amp:.4f})")

        best = results[0]
        print()
        print(f">>> BEST DEVICE: [{best[0]}] {best[1]}")
        print(f">>> Run: python main.py  then enter: {best[0]}")
    else:
        print("  No devices detected audio!")
        print()
        print("Troubleshooting:")
        print("  1. Make sure audio is playing through speakers")
        print("  2. Check if Stereo Mix is enabled and not muted:")
        print("     - Right-click speaker icon -> Sounds -> Recording tab")
        print("     - Right-click Stereo Mix -> Properties -> Levels -> unmute")
        print("  3. Try VB-Cable: https://vb-audio.com/Cable/")


if __name__ == "__main__":
    main()
