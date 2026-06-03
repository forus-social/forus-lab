import json
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate


ACCEL_THRESHOLD = 0.6
GYRO_THRESHOLD  = 0.5


def is_match(accel_score: float, gyro_score: float) -> bool:
    return accel_score >= ACCEL_THRESHOLD and gyro_score >= GYRO_THRESHOLD


def parse_reading(data: dict) -> dict:
    samples = data["samples"]
    keys = ("t", "ax", "ay", "az", "gx", "gy", "gz")
    return {k: np.array([s[k] for s in samples], dtype=np.float64) for k in keys}


def load_reading(path: str) -> dict:
    with open(path) as f:
        return parse_reading(json.load(f))


def plot_axes(parsed_a: dict, parsed_b: dict):
    channels = ("ax", "ay", "az", "gx", "gy", "gz")
    fig, axes = plt.subplots(6, 2, figsize=(12, 10), sharex=False)
    fig.suptitle("Raw sensor channels — left: device A, right: device B")
    for row, ch in enumerate(channels):
        for col, parsed in enumerate((parsed_a, parsed_b)):
            axes[row, col].plot(parsed["t"], parsed[ch], linewidth=0.8)
            axes[row, col].set_ylabel(ch)
            if row == 5:
                axes[row, col].set_xlabel("t")
    plt.tight_layout()
    plt.show()


def resample_to_common_grid(parsed_a: dict, parsed_b: dict, target_hz: float = 10) -> tuple:
    t_start = max(parsed_a["t"][0], parsed_b["t"][0])
    t_end   = min(parsed_a["t"][-1], parsed_b["t"][-1])
    if t_end <= t_start:
        raise ValueError("Recordings have no overlapping time window")
    n = max(2, int((t_end - t_start) / 1000.0 * target_hz))
    t_common = np.linspace(t_start, t_end, n)
    channels = ("ax", "ay", "az", "gx", "gy", "gz")
    def interp(parsed):
        return {"t": t_common, **{ch: np.interp(t_common, parsed["t"], parsed[ch]) for ch in channels}}
    return interp(parsed_a), interp(parsed_b)


def _zscore(v: np.ndarray) -> np.ndarray:
    std = v.std()
    return (v - v.mean()) / std if std > 0 else v - v.mean()


def to_accel_signal(parsed: dict) -> np.ndarray:
    return _zscore(np.sqrt(parsed["ax"]**2 + parsed["ay"]**2 + parsed["az"]**2))


def to_gyro_signal(parsed: dict) -> np.ndarray:
    return _zscore(np.sqrt(parsed["gx"]**2 + parsed["gy"]**2 + parsed["gz"]**2))


def plot_univariate(sig_a: np.ndarray, sig_b: np.ndarray, title: str = "z-scored magnitude"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 3), sharey=True)
    fig.suptitle(title)
    ax1.plot(sig_a, linewidth=0.8)
    ax1.set_title("Device A")
    ax1.set_xlabel("sample")
    ax2.plot(sig_b, linewidth=0.8)
    ax2.set_title("Device B")
    ax2.set_xlabel("sample")
    plt.tight_layout()
    plt.show()


def cross_correlate(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
    a = sig_a - sig_a.mean()
    b = sig_b - sig_b.mean()
    cc = correlate(a, b, mode="full", method="fft")
    energy = np.sqrt((a**2).sum() * (b**2).sum())
    if energy == 0:
        return 0.0
    return float(np.max(np.abs(cc)) / energy)


def assess(parsed_a: dict, parsed_b: dict, plot: bool = False) -> tuple[float, float]:
    """Returns (accel_score, gyro_score), each a normalized cross-correlation in [0, 1]."""
    if plot:
        plot_axes(parsed_a, parsed_b)
    parsed_a, parsed_b = resample_to_common_grid(parsed_a, parsed_b)
    accel_a, accel_b = to_accel_signal(parsed_a), to_accel_signal(parsed_b)
    gyro_a,  gyro_b  = to_gyro_signal(parsed_a),  to_gyro_signal(parsed_b)
    if plot:
        plot_univariate(accel_a, accel_b, title="Accelerometer magnitude (z-scored)")
        plot_univariate(gyro_a,  gyro_b,  title="Gyroscope magnitude (z-scored)")
    return cross_correlate(accel_a, accel_b), cross_correlate(gyro_a, gyro_b)


if __name__ == "__main__":
    import time as _time
    sys.path.insert(0, "scripts")
    from dummy_data_generator import simulate_shake, simulate_independent_shake, to_json_package

    congruous_scores = []
    incongruous_scores = []

    for i in range(10):
        base_ms = int(_time.time() * 1000)
        a, b = simulate_shake()
        accel, gyro = assess(parse_reading(to_json_package(a, "A", base_ms=base_ms)),
                             parse_reading(to_json_package(b, "B", base_ms=base_ms)),
                             plot=False)
        congruous_scores.append((accel, gyro))
        print(f"congruous    {i+1:2d}: accel={accel:.4f}  gyro={gyro:.4f}")

    for i in range(10):
        base_ms = int(_time.time() * 1000)
        a, b = simulate_independent_shake()
        accel, gyro = assess(parse_reading(to_json_package(a, "A", base_ms=base_ms)),
                             parse_reading(to_json_package(b, "B", base_ms=base_ms)),
                             plot=False)
        incongruous_scores.append((accel, gyro))
        print(f"incongruous  {i+1:2d}: accel={accel:.4f}  gyro={gyro:.4f}")

    c = np.array(congruous_scores)
    ic = np.array(incongruous_scores)
    print(f"\nmean congruous:    accel={c[:,0].mean():.4f}  gyro={c[:,1].mean():.4f}")
    print(f"mean incongruous:  accel={ic[:,0].mean():.4f}  gyro={ic[:,1].mean():.4f}")
