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

# modes ---------------------------------------------------------------


def bounce(frame_count: int, minimum_y_divisor: int) -> list[float]:
    loop_count = frame_count // 30
    frame_ranges = [
        (i, i + frame_count // (loop_count * 2))
        for i in range(0, frame_count, frame_count // (loop_count * 2))
    ]

    frame_modifiers = []
    for i, r in enumerate(frame_ranges):
        range_modifiers = (
            numpy.linspace(1.0 / minimum_y_divisor, 1, r[1] - r[0])
            if i % 2 != 0
            else numpy.linspace(1, 1.0 / minimum_y_divisor, r[1] - r[0])
        )
        frame_modifiers.extend(zip([1] * len(range_modifiers), range_modifiers))

    return frame_modifiers


def shrink(frame_count: int, minimum_y_divisor: int) -> list[float]:
    return [
        [1, i]
        for i in numpy.arange(
            1.0,
            1.0 / minimum_y_divisor,
            -((1.0 - (1.0 / minimum_y_divisor)) / frame_count),
        )
    ]


def disappear(frame_count: int) -> list[float]:
    return [[1, 1], *[[0, 0] for _ in range(frame_count - 1)]]


def random_resize(frame_count: int, minimum_divisors: tuple[int]) -> list[float]:
    return [
        [1, 1],
        *[
            [
                random.uniform(1.0 / minimum_divisors[0], 1.0),
                random.uniform(1.0 / minimum_divisors[1], 1.0),
            ]
            for _ in range(frame_count - 1)
        ],
    ]


# helpers --------------------------------------------------------------


def create_frames(input_path: str, frame_path: str) -> str:
    output_path = os.path.join(frame_path, "frame_%04d.jpg")
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", input_path, output_path], capture_output=True
    )

    return re.findall(r"(\d+\.\d+|\d+) fps", proc.stderr.decode("utf-8"))[0]


def ease_modifier(value: int, modifier: float, t_progress: float) -> float:
    # TODO: ease per section for bounce, accounting for min height value
    return max(
        round(value * (modifier ** 2 / (2.0 * (modifier ** 2 - modifier) + 1.0))), 1
    )


def resize_frame(frame_details: tuple) -> None:

    frame_path, frame_modifier, t_progress = frame_details

    image = Image.open(frame_path)
    image = image.resize(
        (
            ease_modifier(image.width, frame_modifier[0], t_progress),
            ease_modifier(image.height, frame_modifier[1], t_progress),
        ),
        Image.LANCZOS,
    )

    image.save(frame_path)


def resize_frames(
    frame_dir: str,
    frame_rate: str,
    modifier: int,
    input_file: str,
    workers: int,
    minimums: tuple[int],
) -> None:

    minimum_divisors = (100 // minimums[0], 100 // minimums[1])

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

    width, height, frame_count = details[0], details[1], details[2]

    if modifier == 1:
        frame_modifiers = bounce(frame_count, minimum_divisors[1])
    elif modifier == 2:
        frame_modifiers = shrink(frame_count, minimum_divisors[1])
    elif modifier == 3:
        frame_modifiers = disappear(frame_count)
    elif modifier == 4:
        frame_modifiers = random_resize(frame_count, minimum_divisors)

    t_progresses = numpy.linspace(0, 1, len(frame_modifiers))

    execution_pool = Pool(processes=workers)
    execution_pool.map(
        resize_frame,
        zip(
            [os.path.join(frame_dir, f) for f in os.listdir(frame_dir)],
            frame_modifiers,
            t_progresses,
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


# main -----------------------------------------------------------------


def main(input_file: str, modifier: int, workers: int, minimums: tuple[int]) -> None:
    if os.path.exists("./temp"):
        shutil.rmtree(path="temp")

    os.makedirs("./temp/frames")

    # create image for every frame in video

    print("[+] Creating Frames...")
    frame_rate = create_frames(input_file, "./temp/frames")

    # resize frames based on chosen modifier

    print("[+] Resizing Frames...")
    resize_frames("./temp/frames", frame_rate, modifier, input_file, workers, minimums)

    # convert each frame to webm format

    print("[+] Converting Frames...")
    convert_frames("./temp/frames", frame_rate, workers)

    # combine all webm frames into one video

    with open("input.txt", "w+") as f:
        f.write(
            "\n".join(
                [
                    f"file '{os.path.join('./temp/frames', path)}'"
                    for path in os.listdir("./temp/frames")
                ]
            )
        )

    print("[+] Combining Frames...")
    combine_frames("input.txt")

    # add the audio from the original input to the output video

    print("[+] Adding Audio...")
    output_file_name = add_audio(input_file, "./temp/first_pass_output.webm")

    # delete temp files and concatenation input file

    print("[+] Perfoming Clean-Up...")
    os.remove("input.txt")
    shutil.rmtree("./temp")

    # video is complete and has been output as `output_file_name`

    print(f"[+] Video saved as {output_file_name}")


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
    parser.add_argument(
        "-mw",
        "-min-width",
        type=int,
        default=1,
        help="Use a percentage to specify the minimum width a frame can be modified to (defaults to 1%)",
    )
    parser.add_argument(
        "-mh",
        "-min-height",
        type=int,
        default=1,
        help="Use a percentage to specify the minimum height a frame can be modified to (defaults to 1%)",
    )
    args = parser.parse_args()

    if args.workers is None:
        args.workers = os.cpu_count() or 1

    main(args.input, args.modifier, args.workers, (args.mw, args.mh))
