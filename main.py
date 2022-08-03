import argparse
import os
import random
import re
import shutil
import string
import subprocess
from multiprocessing import Pool

import numpy
from PIL import Image


def bouncing_video(frame_count: int) -> list[float]:
    loop_count = frame_count // 30  # maintain similar transition speed for all videos
    frame_ranges = [
        (i, i + frame_count // (loop_count * 2))
        for i in range(0, frame_count, frame_count // (loop_count * 2))
    ]

    frame_modifiers = [
        1.0 - (n - s[1][0]) / (s[1][1] - s[1][0])
        if s[0] % 2 != 0
        else (n - s[1][0]) / (s[1][1] - s[1][0])
        for n, s in zip(
            range(1, frame_count + 1),
            [
                next(
                    (
                        (i + 1, frame_ranges[i])
                        for i in range(len(frame_ranges))
                        if n - 1 in range(*frame_ranges[i])
                    ),
                    None,
                )
                for n in range(1, frame_count + 1)
            ],
        )
    ]

    return frame_modifiers


def shrinking_video(frame_count: int) -> list[float]:
    return [i for i in numpy.arange(1.0, 0.0, -(1.0 / frame_count))]


def create_frames(input_path: str, frame_path: str) -> str:
    output_path = os.path.join(frame_path, "frame_%04d.jpg")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", input_path, output_path], capture_output=True
    )

    return re.findall(r"(\d+\.\d+|\d+) fps", proc.stderr.decode("utf-8"))[0]


def resize_frame(frame_details: tuple) -> None:
    frame_path, frame_modifier = frame_details

    image = Image.open(frame_path)
    image = image.resize(
        (
            image.width,
            max(
                round(
                    image.height
                    * (
                        frame_modifier**2
                        / (2.0 * (frame_modifier**2 - frame_modifier) + 1.0)
                    )
                ),
                1,
            ),
        ),
        Image.Resampling.LANCZOS,
    )

    image.save(frame_path)


def resize_frames(
    frame_dir: str, frame_rate: str, modifier: int, input_file: str, workers: int
) -> None:

    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-count_packets",
            "-show_entries",
            "stream=width,height,nb_read_packets",
            "-of",
            "csv=p=0",
            input_file,
        ],
        capture_output=True,
    )

    details = list(map(int, proc.stdout.decode("utf-8").split("\n")[0].split(",")))

    width, height = details[0], details[1]
    frame_count = details[2]

    if modifier == 1:
        frame_modifiers = bouncing_video(frame_count)
    elif modifier == 2:
        frame_modifiers = shrinking_video(frame_count)

    execution_pool = Pool(processes=workers)
    execution_pool.map(
        resize_frame,
        zip(
            [os.path.join(frame_dir, f) for f in os.listdir(frame_dir)],
            frame_modifiers,
        ),
    )


def convert_frame(frame_details: tuple) -> None:
    frame_path, frame_rate = frame_details

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            frame_rate,
            "-f",
            "image2",
            "-i",
            frame_path,
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            frame_path[:-4] + ".webm",
        ]
    )

    os.remove(frame_path)


def convert_frames(frame_dir: str, frame_rate: str, workers: int) -> None:
    execution_pool = Pool(processes=workers)
    execution_pool.map(
        convert_frame,
        [(os.path.join(frame_dir, f), frame_rate) for f in os.listdir(frame_dir)],
    )


def combine_frames(input_files: str) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            input_files,
            "-c",
            "copy",
            "-y",
            os.path.join("./temp", "first_pass_output.webm"),
        ]
    )


def add_audio(input_video: str, output_video: str) -> str:
    output_file_name = f"output_{''.join([random.choice(string.ascii_letters) for _ in range(5)])}.webm"

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            input_video,
            "-i",
            output_video,
            "-map",
            "1:v",
            "-map",
            "0:a",
            "-c:v",
            "copy",
            "-y",
            output_file_name,
        ]
    )

    return output_file_name


def main(input_file: str, modifier: int, workers: int) -> None:
    if os.path.exists("./temp"):
        shutil.rmtree(path="temp")

    os.makedirs("./temp/frames")

    # create image for every frame in video

    print("- Creating Frames...")

    frame_rate = create_frames(input_file, "./temp/frames")

    # resize frames

    print("- Resizing Frames...")

    resize_frames("./temp/frames", frame_rate, modifier, input_file, workers)

    # convert frames to webm

    print("- Converting Frames...")

    convert_frames("./temp/frames", frame_rate, workers)

    # combine frames into video

    with open("input.txt", "w+") as f:
        for path in os.listdir("./temp/frames"):
            f.write(f"file '{os.path.join('./temp/frames', path)}'\n")

    print("- Combining Frames...")

    combine_frames("input.txt")

    # add audio to video...

    print("- Adding Audio...")

    output_file_name = add_audio(input_file, "./temp/first_pass_output.webm")

    # clean up

    print("- Perfoming Clean-Up...")

    os.remove("input.txt")
    shutil.rmtree("./temp")

    # finished

    print("- Video saved as: " + output_file_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a webm video with a dynamic resolution."
    )
    parser.add_argument(
        "-i", "--input", type=str, help="Input video file", required=True
    )
    parser.add_argument(
        "-m", "--modifier", type=int, help="Video modifier option", required=True
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        help="Number of workers/threads to run (defaults to CPU thread count)",
    )
    args = parser.parse_args()
    if args.workers is None:
        args.workers = os.cpu_count() or 1
    main(args.input, args.modifier, args.workers)