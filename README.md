# dynamic-webm

Create a webm video that changes size when played in a web application.

```
python main.py -i/--input <input_video> -m/--modifier <modification_option>
```

- `-i/--input` - path of video to be modified
- `-m/--modifier` - modification option
- `-w/--workers` - number of workers to use for processing (default: CPU thread count)

### Modification Options

- `1` - Create a "bouncing" video. The video will shrik and grow multiple times along the Y axis.
- `2` - Create a "shrinking" video. The video will shrink along the Y axis to a height of 1 pixel.
- `3` - Create a "disappearing" video. The video will shrink to a resolution of 1x1.
- `4` - Create a "random" video. Video frames will change to random resolutions.

### Example Result

`Bouncing Video`


[example.webm](https://user-images.githubusercontent.com/45544056/182500464-c14adb3d-9396-4821-b89a-558e1dbdeca7.webm)
