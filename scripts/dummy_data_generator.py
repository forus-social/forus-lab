import numpy as np

def simulate_shake(duration=5.0, sample_rate=100, sigma_shared=1.0, 
                   sigma_noise=0.05, sigma_axis_offset=0.1):
    """
    Simulate two phones shaken together.
    
    duration: seconds of recording
    sample_rate: Hz (100 is realistic for mobile IMU)
    sigma_shared: intensity of the shared motion
    sigma_noise: per-device sensor noise
    sigma_axis_offset: simulates slight physical misalignment between devices
    """
    n = int(duration * sample_rate)
    t = np.linspace(0, duration, n)
    
    # --- shared motion (what both phones experience) ---
    # random walk with some smoothing to simulate human shaking
    shared_accel = np.zeros((n, 3))
    shared_gyro = np.zeros((n, 3))
    
    for axis in range(3):
        # random impulses smoothed with a rolling window
        impulses = np.random.normal(scale=sigma_shared, size=n)
        shared_accel[:, axis] = np.convolve(impulses, 
                                 np.ones(10)/10, mode='same')
        shared_gyro[:, axis] = np.convolve(
                                np.random.normal(scale=sigma_shared*0.5, size=n),
                                np.ones(10)/10, mode='same')
    
    # --- per-device noise ---
    noiseA_accel = np.random.normal(scale=sigma_noise, size=(n, 3))
    noiseB_accel = np.random.normal(scale=sigma_noise, size=(n, 3))
    noiseA_gyro  = np.random.normal(scale=sigma_noise, size=(n, 3))
    noiseB_gyro  = np.random.normal(scale=sigma_noise, size=(n, 3))
    
    # --- axis misalignment (phone B is physically flipped/offset) ---
    # simple approximation: swap and negate some axes
    axis_offset = np.array([1, -1, 1]) + np.random.normal(
                            scale=sigma_axis_offset, size=3)
    
    # --- time offset (phones didn't start recording at exactly the same ms) ---
    time_offset_samples = np.random.randint(0, 10)  # up to 100ms offset
    
    phoneA = {
        "t": t,
        "ax": (shared_accel + noiseA_accel)[:,0],
        "ay": (shared_accel + noiseA_accel)[:,1],
        "az": (shared_accel + noiseA_accel)[:,2],
        "gx": (shared_gyro  + noiseA_gyro)[:,0],
        "gy": (shared_gyro  + noiseA_gyro)[:,1],
        "gz": (shared_gyro  + noiseA_gyro)[:,2]
    }
    phoneB_accel = (shared_accel * axis_offset + noiseB_accel)
    phoneB_gyro  = (shared_gyro  * axis_offset + noiseB_gyro)
    
    # apply time offset by rolling the array
    phoneB = {
        "t": t,
        "ax": (np.roll(phoneB_accel, time_offset_samples, axis=0))[:,0],
        "ay": (np.roll(phoneB_accel, time_offset_samples, axis=0))[:,1],
        "az": (np.roll(phoneB_accel, time_offset_samples, axis=0))[:,2],
        "gx": (np.roll(phoneB_gyro,  time_offset_samples, axis=0))[:,0],
        "gy": (np.roll(phoneB_gyro,  time_offset_samples, axis=0))[:,1],
        "gz": (np.roll(phoneB_gyro,  time_offset_samples, axis=0))[:,2],
    }
    
    return phoneA, phoneB

def simulate_independent_shake(duration=5.0, sample_rate=100, sigma=1.0):
    """
    Simulate two phones shaken independently (should NOT match).
    """
    n = int(duration * sample_rate)
    t = np.linspace(0, duration, n)

    def make_phone():
        accel = np.zeros((n, 3))
        gyro  = np.zeros((n, 3))
        for axis in range(3):
            accel[:, axis] = np.convolve(
                np.random.normal(scale=sigma, size=n),
                np.ones(10)/10, mode='same')
            gyro[:, axis] = np.convolve(
                np.random.normal(scale=sigma * 0.5, size=n),
                np.ones(10)/10, mode='same')
        return {
            "t": t,
            "ax": accel[:, 0], "ay": accel[:, 1], "az": accel[:, 2],
            "gx": gyro[:, 0],  "gy": gyro[:, 1],  "gz": gyro[:, 2],
        }

    return make_phone(), make_phone()


def to_json_package(phone_dict, device_id="phone", session_id="session"):
    t = phone_dict["t"]
    samples = [
        {
            "t": int(i),
            "ax": float(phone_dict["ax"][i]),
            "ay": float(phone_dict["ay"][i]),
            "az": float(phone_dict["az"][i]),
            "gx": float(phone_dict["gx"][i]),
            "gy": float(phone_dict["gy"][i]),
            "gz": float(phone_dict["gz"][i]),
        }
        for i in range(len(t))
    ]
    return {"device_id": device_id, "session_id": session_id, "samples": samples}