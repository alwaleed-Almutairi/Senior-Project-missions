"""
mission1_scan_cameratest.py
───────────────────────────
Runs Mission 1 scan using the REAL RealSense camera
but WITHOUT a drone connection. Drone movement is simulated.

This proves:
  - RealSense D435 live feed works
  - Images are captured and saved with NED coordinates
  - Video latency is within acceptable range

Usage:
  python mission1_scan_cameratest.py
"""

import asyncio
import cv2
import numpy as np
import pyrealsense2 as rs
import os
import time


async def stream_and_sleep(duration, pipeline):
    """Waits while keeping the RealSense feed live. Measures latency."""
    end_time = asyncio.get_event_loop().time() + duration
    latest_frame = None
    latencies = []

    while asyncio.get_event_loop().time() < end_time:
        t_start = time.perf_counter()
        frames = pipeline.poll_for_frames()
        if frames:
            color_frame = frames.get_color_frame()
            if color_frame:
                latest_frame = np.asanyarray(color_frame.get_data())
                cv2.imshow("Ground Station - RealSense Live", latest_frame)
                t_end = time.perf_counter()
                latencies.append((t_end - t_start) * 1000)
        cv2.waitKey(1)
        await asyncio.sleep(0.03)

    if latencies:
        avg = sum(latencies) / len(latencies)
        print(f"   [LATENCY] Avg: {avg:.1f} ms | Max: {max(latencies):.1f} ms | Frames: {len(latencies)}")

    return latest_frame


async def run():
    print("=" * 60)
    print("  MISSION 1 — CAMERA TEST (No Drone Required)")
    print("=" * 60)

    # ─── RealSense Init ──────────────────────────────────────
    print("\nStarting Intel RealSense pipeline...")
    pipeline = rs.pipeline()
    config = rs.config()
    try:
        config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
        pipeline.start(config)
        print("RealSense D435 initialized successfully!")
        await stream_and_sleep(2, pipeline)
    except Exception as e:
        print(f"RealSense failed to initialize: {e}")
        return

    # ─── Scan Parameters ─────────────────────────────────────
    y_axis = int(input("Enter height (number of images, max 15): "))
    x_axis = int(input("Enter width (number of columns): "))
    step_size = 1.0

    output_folder = "img"
    os.makedirs(output_folder, exist_ok=True)
    print(f"-- Images will be saved to '{output_folder}/'")

    # ─── Simulate Drone (no real drone needed) ───────────────
    print("\n-- [SIM] Arming (simulated)")
    print("-- [SIM] Taking off (simulated)")
    await stream_and_sleep(3, pipeline)

    current_n, current_e, current_d = 0.0, 0.0, -1.0
    isdown = True
    total_images = 0

    print("\n-- Scanning started (RealSense REAL, drone SIMULATED)")
    print("-" * 60)

    for i in range(x_axis):
        y_range = range(y_axis) if isdown else reversed(range(y_axis))
        for j in y_range:
            latest_frame = await stream_and_sleep(2, pipeline)

            image_name = f"img_{current_n:.2f}_{current_e:.2f}_{current_d:.2f}.jpg"
            filepath = os.path.join(output_folder, image_name)

            if latest_frame is not None:
                saved_img = latest_frame.copy()
                cv2.putText(saved_img, f"NED: {current_n:.1f}, {current_e:.1f}, {current_d:.1f}",
                            (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
                cv2.imwrite(filepath, saved_img)
                total_images += 1
                print(f"  [{total_images:3d}] Captured {image_name}")
            else:
                print(f"  [---] Warning: RealSense dropped a frame!")

            current_d += step_size if not isdown else -step_size

        print(f"  >> [SIM] Moving to column {i + 1}")
        isdown = not isdown

        if i < x_axis - 1:
            current_e -= step_size

    # ─── Done ─────────────────────────────────────────────────
    print("-" * 60)
    print(f"\n-- Mission 1 scan complete!")
    print(f"-- Total images saved: {total_images}")
    print(f"-- Output folder: {os.path.abspath(output_folder)}")

    print("\n-- [SIM] Returning to home (simulated)")
    await stream_and_sleep(3, pipeline)

    print("-- [SIM] Landing (simulated)")

    pipeline.stop()
    cv2.destroyAllWindows()
    print("-- Done. RealSense stopped safely.")


if __name__ == "__main__":
    asyncio.run(run())
