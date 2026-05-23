import json
import sys
import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import correlate


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


def to_univariate(parsed: dict) -> np.ndarray:
    accel_mag = np.sqrt(parsed["ax"]**2 + parsed["ay"]**2 + parsed["az"]**2)
    gyro_mag  = np.sqrt(parsed["gx"]**2 + parsed["gy"]**2 + parsed["gz"]**2)

    def zscore(v):
        std = v.std()
        return (v - v.mean()) / std if std > 0 else v - v.mean()

    return zscore(accel_mag) + zscore(gyro_mag)


def plot_univariate(sig_a: np.ndarray, sig_b: np.ndarray):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 3), sharey=True)
    fig.suptitle("Univariate signal (z-scored accel mag + gyro mag)")
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


def assess(parsed_a: dict, parsed_b: dict, plot: bool = True) -> float:
    if plot:
        plot_axes(parsed_a, parsed_b)
    sig_a = to_univariate(parsed_a)
    sig_b = to_univariate(parsed_b)
    if plot:
        plot_univariate(sig_a, sig_b)
    return cross_correlate(sig_a, sig_b)


if __name__ == "__main__":
    sys.path.insert(0, "scripts")
    from dummy_data_generator import simulate_shake, simulate_independent_shake, to_json_package

    congruous_scores = []
    incongruous_scores = []

    for i in range(10):
        a, b = simulate_shake()
        score = assess(parse_reading(to_json_package(a, "A")),
                       parse_reading(to_json_package(b, "B")),
                       plot=False)
        congruous_scores.append(score)
        print(f"congruous    {i+1:2d}: {score:.4f}")

    for i in range(10):
        a, b = simulate_independent_shake()
        score = assess(parse_reading(to_json_package(a, "A")),
                       parse_reading(to_json_package(b, "B")),
                       plot=False)
        incongruous_scores.append(score)
        print(f"incongruous  {i+1:2d}: {score:.4f}")

    print(f"\nmean congruous:    {np.mean(congruous_scores):.4f}")
    print(f"mean incongruous:  {np.mean(incongruous_scores):.4f}")
