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


def modifier_bounce(frames: int, width: int, height: int, min_y: float, *, ease: bool = False) -> list[float]:
    """Designed to simulate a bouncing effect on the y axis.

    Args:
        frames (int): Total number of frames in the video.
        width (int): Original width of the video.
        height (int): Original height of the video.
        min_y (float): Minimum height of the video represented as a decimal fraction between 0 and 1.
        ease (bool, optional): Speficy whether an easing effect should be applied to the transition. Defaults to False.

    Returns:
        list[float]: A list of tuples containing the modified width and height of each frame.
    """
    range_size = frames // (frames // 30 * 2)
    modified = []
    range_start = 0
    transition_switch = True

    for i in range(frames):
        progress = (i - range_start) / range_size

        if transition_switch:
            modifier = apply_easing(progress) if ease else progress
        else:
            modifier = apply_easing(1 - progress) if ease else 1 - progress

        modified.append((width, int(height + (height * min_y - height) * modifier)))

        if i - range_start == range_size - 1:
            range_start += range_size
            transition_switch = not transition_switch

    return modified


def modifier_shrink(frames: int, width: int, height: int, min_y: float, *, ease: bool = False) -> list[float]:
    """Designed to simulate a shrinking effect on the y axis.

    Args:
        frames (int): Total number of frames in the video.
        width (int): Original width of the video.
        height (int): Original height of the video.
        min_y (float): Minimum height of the video represented as a decimal fraction between 0 and 1.
        ease (bool, optional): Speficy whether an easing effect should be applied to the transition. Defaults to False.

    Returns:
        list[float]: A list of tuples containing the modified width and height of each frame.
    """
    modified = []

    if not ease:
        height_steps = np.arange(1.0, min_y, -((1.0 - (min_y)) / frames))
        modified = map(lambda x: (width, int(height * x)), height_steps)
    else:
        for i in range(frames):
            height_modifier = (height * min_y - height) * apply_easing((i + 1) / frames)
            modified.append((width, int(height + height_modifier)))

    return modified


def modifier_vanish(frames: int, width: int, height: int) -> list[float]:
    """Designed to a make the video "disappear" as soon as it starts.


    Args:
        frames (int): Total number of frames in the video.
        width (int): Original width of the video.
        height (int): Original height of the video.

    Returns:
        list[float]: A list of tuples containing the modified width and height of each frame.
    """
    modified = [(width, height)] + [[1, 1]] * (frames - 1)

    return modified


def modifier_random(frames: int, width: int, height: int, min_x: float, min_y: float) -> list[float]:
    """Designed to rapidly change the dimensions of the video.

    Args:
        frames (int): Total number of frames in the video.
        width (int): Original width of the video.
        height (int): Original height of the video.
        min_x (float): Minimum width of the video represented as a decimal fraction between 0 and 1.
        min_y (float): Minimum height of the video represented as a decimal fraction between 0 and 1.

    Returns:
        list[float]: A list of tuples containing the modified width and height of each frame.
    """
    modified = [(width, height)]

    for _ in range(frames - 1):
        modified_width = int(width * random.uniform(min_x, 1))
        modified_height = int(height * random.uniform(min_y, 1))
        modified.append((modified_width, modified_height))

    return modified


def apply_easing(t: float) -> float:
    """Apply quadratic easing to a value.

    Args:
        t (float): Progress represented as a decimal fraction between 0 and 1.

    Returns:
        float: Modified (eased) progress represented as a decimal fraction between 0 and 1.
    """
    if t < 0.5:
        return 2 * t * t
    return (-2 * t * t) + (4 * t) - 1


def deconstruct_video(input_path: str, output_path: str) -> str:
    """Deconstruct a video into a series of frames.

    Args:
        input_path (str): Complete path to the input video.
        output_path (str): Complete path to the output directory (where frames will be stored).

    Returns:
        str: Returns the framerate of the input video.
    """
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
    """Resize an individual frame/image based on speficied details.

    Args:
        details (tuple): A tuple containing the path to the frame and the modified width and height of the frame.
    """
    frame_path, dimensions = details

    img = (Image.open(frame_path)).resize((max(dimensions[0], 1), max(dimensions[1], 1)), Image.LANCZOS)
    img.save(frame_path)


def resize_frames(
    frame_dir: str, modifier: int, input_path: str, threads: int, min_width: int, min_height: int, ease: bool = False
) -> None:
    """Resize all video frames based on the specified options. Uses multiprocessing with the resize_frame function.

    Args:
        frame_dir (str): Directory of the deconstructed video frames.
        modifier (int): Choice of modifier function to use.
        input_path (str): Path of the input video.
        threads (int): Number of Threads/Workers to use when resizing frames concurrently.
        min_width (int): Minimum width of the video represented as a percentage.
        min_height (int): Minimum height of the video represented as a percentage.
        ease (bool): Speficy whether an easing effect should be applied to the transition. Defaults to False.
    """
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

    width, height, frame_count = list(map(int, process.stdout.decode("utf-8").split("\n")[0].split(",")))

    if modifier == 1:
        modified_sizes = modifier_bounce(frame_count, width, height, min_y, ease=ease)
    elif modifier == 2:
        modified_sizes = modifier_shrink(frame_count, width, height, min_y, ease=ease)
    elif modifier == 3:
        modified_sizes = modifier_vanish(frame_count, width, height)
    elif modifier == 4:
        modified_sizes = modifier_random(frame_count, width, height, min_x, min_y)

    pool = multiprocessing.Pool(processes=threads)
    pool.map(
        resize_frame,
        zip([os.path.join(frame_dir, f) for f in os.listdir(frame_dir)], modified_sizes),
    )


def convert_frame(details: tuple) -> None:
    """Convert a single image frame to WEBM format.

    Args:
        details (tuple): A tuple containing the path to the frame and the frame rate of the video.
    """
    frame_path, frame_rate, quality = details

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
            "-crf",
            quality,
            frame_path[:-4] + ".webm",
        ]
    )

    os.remove(frame_path)


def convert_frames(frame_dir: str, frame_rate: str, threads: int) -> None:
    """Convert all frames to WEBM format. Uses multiprocessing with the convert_frame function.

    Args:
        frame_dir (str): Directory of the deconstructed video frames.
        frame_rate (str): Frame rate of the input video.
        threads (int): Number of Threads/Workers to use when converting frames.
    """
    pool = multiprocessing.Pool(processes=threads)
    pool.map(
        convert_frame,
        [(os.path.join(frame_dir, f), frame_rate) for f in os.listdir(frame_dir)],
    )


def combine_frames(input_list: str) -> None:
    """Combine all processed frames (WEBM format) into a single video.

    Args:
        input_list (str): String containing a list of paths of all WEBM formatted frames.
    """
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
    """Add the original audio track to the modified video.

    Args:
        input_path (str): Path of the original video.
        modified_path (str): Path of the modified video.

    Returns:
        str: Name of the final output file.
    """
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


def main(args: argparse.Namespace) -> None:
    """Main function of the program. Illustrates the process from start to finish.

    Args:
        args (argparse.Namespace): Arguments passed in from the command line.
    """
    if os.path.exists("./temp"):
        shutil.rmtree(path="temp")

    os.makedirs("./temp/frames")

    print("[+] Creating Frames...")
    frame_rate = deconstruct_video(args.input, "./temp/frames")

    print("[+] Resizing Frames...")
    resize_frames("./temp/frames", args.modifier, args.input, args.threads, args.minwidth, args.minheight, args.ease)

    print("[+] Converting Frames...")
    convert_frames("./temp/frames", frame_rate, args.threads, args.quality)

    with open("./temp/input.txt", "w+") as file:
        file.write("\n".join([f"file '{os.path.join('frames', p)}'" for p in os.listdir("./temp/frames")]))

    print("[+] Combining Frames...")
    combine_frames("./temp/input.txt")

    print("[+] Adding Audio...")
    output_name = add_audio(args.input, os.path.join("./temp", "first_pass_output.webm"))

    print("[+] Cleaning Up...")
    shutil.rmtree(path="temp")

    print("[+] Output Saved -> {}".format(output_name))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a WEBM video that changes resolution when played.")
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
    parser.add_argument(
        "-q",
        "--quality",
        type=int,
        default=23,
        help="Set the quality of the output video (0 = lossless, 51 = worst possible quality. defaults to 23).",
        choices=range(0, 52)    
    )

    args = parser.parse_args()

    if not (0 <= args.minwidth <= 100) or not (0 <= args.minheight <= 100):
        print("Minimum width and height percentages must be between 0 and 100.")
        exit(1)

    if args.threads is None:
        args.threads = os.cpu_count() or 1

    main(args)
