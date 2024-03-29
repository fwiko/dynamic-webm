# Dynamic WEBM

Create a WEBM video that changes resolution when played. With options to set the minimum height/width and to enable easing transitions.

### Options

|      Flag      |                                               Description                                               |
| :------------: | :-----------------------------------------------------------------------------------------------------: |
|  -i, --input   |                                The path of the video you wish to modify.                                |
| -m, --modifier |                                 An option from the available Modifiers.                                 |
| -w, --workers  |                  Number of workers to use for processing (default: CPU Thread Count).                   |
|   --minwidth   |      Minimum width that the video can be modified to, understood as a percentage of the original.       |
|  --minheight   |      Minimum height that the video can be modified to, understood as a percentage of the original.      |
|     --ease     | Enable bidirectional cubic easing transitions with the bouncing, shrinking, and disappearing modifiers. |

### Modifiers

| Modifier  | Value |                                                                           Description                                                                            |
| :-------: | :---: | :--------------------------------------------------------------------------------------------------------------------------------------------------------------: |
|  Bounce   |   1   |                                    Create a "bouncing" video; The video will shrink and grow multiple times along the Y axis.                                    |
|  Shrink   |   2   |      Create a "shrinking" video; The video will shrink along the Y axis to a final height of 1 pixel, or the height specified using the `--minheight` flag.      |
| Disappear |   3   |                              Create a "vanishing" video; The video will instantly change to a resolution of 1x1 upon being played.                               |
|  Random   |   4   | Create a "random" video; Every frame of the video will be set to a random resolution, within the constraints of specified `--minheight` and `--minwidth` values. |

### Pre-requisites

- FFmpeg (https://ffmpeg.org/)

### Example

```bash
python main.py -i <input_path> -m bounce --minheight 5 --ease
```

[example.webm](https://github.com/fwiko/dynamic-webm/assets/45544056/c1a1672d-85eb-414e-9ca4-488fe31f695f)
