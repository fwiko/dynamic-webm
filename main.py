import argparse
import multiprocessing
import os
import random
import re
import shutil
import string
import subprocess

import numpy as np
from PIL import Image


# Modifiers ------------------------------------------------------------------


def modifier_bounce(frames, width, height, min_y, *, ease=False) -> list[float]:
    range_size = frames // (frames // 30 * 2)
    modified = []
    range_start = 0
    transition_switch = True

    for i in range(frames):
        progress = (i - range_start) / range_size

        if transition_switch:
            modifier = ease_step(progress) if ease else progress
        else:
            modifier = ease_step(1 - progress) if ease else 1 - progress

        modified.append((width, int(height + (height * min_y - height) * modifier)))

        if i - range_start == range_size - 1:
            range_start += range_size
            transition_switch = not transition_switch

    return modified


def modifier_shrink(frames, width, height, min_y, *, ease: bool = False) -> list[float]:
    modified = []

    if not ease:
        modified = map(
            lambda x: (width, int(height * x)), get_height_steps(frames, min_y)
        )
    else:
        for i in range(frames):
            height_modifier = (height * min_y - height) * ease_step((i + 1) / frames)
            modified.append((width, int(height + height_modifier)))

    return modified


def modifier_vanish(f_count: int, f_width: int, f_height: int) -> list[float]:
    return [[f_width, f_height], *[[1, 1]] * (f_count - 1)]


def modifier_random(
    f_count: int, f_width: int, f_height: int, min_x: float, min_y: float
) -> list[float]:
    return [
        [f_width, f_height],
        *[
            [
                int(np.random.uniform(1.0 * min_x, 1.0) * f_width),
                int(np.random.uniform(1.0 * min_y, 1.0) * f_height),
            ]
            for _ in range(f_count - 1)
        ],
    ]


# Helpers --------------------------------------------------------------------


def get_height_steps(f_count: int, min_y: float) -> list[float]:
    return np.arange(1.0, min_y, -((1.0 - (min_y)) / f_count))


def get_width_steps(f_count: int, min_x: float) -> list[float]:
    return np.arange(1.0, min_x, -((1.0 - (min_x)) / f_count))


def ease_step(t: float) -> float:
    if t < 0.5:
        return 2 * t * t
    return (-2 * t * t) + (4 * t) - 1


def log(message: str) -> None:
    print(f"[+] {message}")


def deconstruct_video(input_path: str, output_path: str) -> str:
    process = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            input_path,
            os.path.join(output_path, "frame_%05d.png"),
        ],
        capture_output=True,
    )
    return re.findall(r"(\d+\.\d+|\d+) fps", process.stderr.decode("utf-8"))[0]


def resize_frame(details: tuple) -> None:
    f_path, dimensions = details

    img = (Image.open(f_path)).resize(
        (max(dimensions[0], 1), max(dimensions[1], 1)), Image.LANCZOS
    )
    img.save(f_path)


def resize_frames(
    f_dir: str,
    f_rate: str,
    modifier_option: int,
    input_path: str,
    threads: int,
    min_width: int,
    min_height: int,
    ease: bool,
) -> None:
    min_x = min_width / 100
    min_y = min_height / 100

    process = subprocess.run(
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
            input_path,
        ],
        capture_output=True,
    )

    width, height, frame_count = list(
        map(int, process.stdout.decode("utf-8").split("\n")[0].split(","))
    )

    if modifier_option == 1:
        modified_sizes = modifier_bounce(frame_count, width, height, min_y, ease=ease)
    elif modifier_option == 2:
        modified_sizes = modifier_shrink(frame_count, width, height, min_y, ease=ease)
    elif modifier_option == 3:
        modified_sizes = modifier_vanish(frame_count, width, height)
    elif modifier_option == 4:
        modified_sizes = modifier_random(frame_count, width, height, min_x, min_y)

    pool = multiprocessing.Pool(processes=threads)
    pool.map(
        resize_frame,
        zip([os.path.join(f_dir, f) for f in os.listdir(f_dir)], modified_sizes),
    )


def convert_frame(details: tuple) -> None:
    f_path, f_rate = details

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            f_rate,
            "-f",
            "image2",
            "-i",
            f_path,
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            f_path[:-4] + ".webm",
        ]
    )

    os.remove(f_path)


def convert_frames(f_dir: str, f_rate: str, workers: int) -> None:
    pool = multiprocessing.Pool(processes=workers)
    pool.map(
        convert_frame,
        [(os.path.join(f_dir, f), f_rate) for f in os.listdir(f_dir)],
    )


def combine_frames(input_list: str) -> None:
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
            input_list,
            "-c",
            "copy",
            "-y",
            os.path.join("./temp", "first_pass_output.webm"),
        ]
    )


def add_audio(input_path: str, modified_path: str) -> str:
    output_name = f"output_{''.join([random.choice(string.ascii_letters) for _ in range(5)])}.webm"

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            input_path,
            "-i",
            modified_path,
            "-map",
            "1:v",
            "-map",
            "0:a",
            "-c:v",
            "copy",
            "-y",
            output_name,
        ]
    )

    return output_name


# Main -----------------------------------------------------------------------


def main(args: argparse.Namespace) -> None:
    if os.path.exists("./temp"):
        shutil.rmtree(path="temp")

    os.makedirs("./temp/frames")

    log("Creating Frames...")
    f_rate = deconstruct_video(args.input, "./temp/frames")

    log("Resizing Frames...")
    resize_frames(
        "./temp/frames",
        f_rate,
        args.modifier,
        args.input,
        args.threads,
        args.minwidth,
        args.minheight,
        args.ease,
    )

    log("Converting Frames...")
    convert_frames("./temp/frames", f_rate, args.threads)

    with open("./temp/input.txt", "w+") as file:
        file.write(
            "\n".join(
                [
                    f"file '{os.path.join('frames', p)}'"
                    for p in os.listdir("./temp/frames")
                ]
            )
        )

    log("Combining Frames...")
    combine_frames("./temp/input.txt")

    log("Adding Audio...")
    output_name = add_audio(
        args.input, os.path.join("./temp", "first_pass_output.webm")
    )

    log("Cleaning Up...")
    shutil.rmtree(path="temp")

    log("Video Saved -> {}".format(output_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Create a WEBM video that changes resolution when played."
    )
    parser.add_argument(
        "-i",
        "--input",
        type=str,
        help="Path of video file that will be modified.",
        required=True,
    )
    parser.add_argument(
        "-m",
        "--modifier",
        type=int,
        help="Choice of video modifier option.",
        choices=range(1, 5),
        required=True,
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        help="Number of workers to use (defaults to CPU thread count).",
    )
    parser.add_argument(
        "--minwidth",
        type=int,
        default=0,
        help="Use a percentage to specify the minimum width a frame can be modified to (defaults to 0%).",
    )
    parser.add_argument(
        "--minheight",
        type=int,
        default=0,
        help="Use a percentage to specify the minimum width a frame can be modified to (defaults to 0%).",
    )
    parser.add_argument(
        "--ease",
        action="store_true",
        help="Enable smooth transitions for the bounce and shrink modifiers.",
    )

    args = parser.parse_args()

    if not (0 <= args.minwidth <= 100) or not (0 <= args.minheight <= 100):
        print("Minimum width and height percentages must be between 0 and 100.")
        exit(1)

    if args.threads is None:
        args.threads = os.cpu_count() or 1

    main(args)
