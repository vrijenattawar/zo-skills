---
name: remotion
description: Create videos programmatically with React using Remotion. Scaffold projects, write compositions, and render MP4s. Zo-optimized wrapper around official Remotion agent skills.
compatibility: Created for Zo Computer
metadata:
  author: <YOUR_HANDLE>.zo.computer
  upstream: remotion-dev/skills
  tags: video, react, animation, rendering, media
---

## When to Use

Use this skill when:
- Creating programmatic videos from code (not generative AI video)
- Building data-driven video content (charts, stats, personalized videos)
- Producing batch videos from templates + data
- Creating animated social content (TikTok, Reels, Shorts)
- Building product/explainer videos with precise control

## Quick Start

### 1. Create a New Project
```bash
python3 Skills/remotion/scripts/remotion_cli.py new my-video --template blank
cd Sites/my-video
```

### 2. Write Your Composition
Edit `src/Composition.tsx` - this is your video defined as React components.

### 3. Preview in Studio
```bash
python3 Skills/remotion/scripts/remotion_cli.py studio my-video
```

### 4. Render to MP4
```bash
python3 Skills/remotion/scripts/remotion_cli.py render my-video --output output.mp4
```

## Core Concepts

### Compositions
A composition defines your video's dimensions, duration, and fps:
```tsx
<Composition
  id="MyVideo"
  component={MyComponent}
  durationInFrames={300}  // 10 seconds at 30fps
  fps={30}
  width={1920}
  height={1080}
/>
```

### Frame-Based Animation
ALL animations MUST use `useCurrentFrame()`. CSS animations are FORBIDDEN.
```tsx
const frame = useCurrentFrame();
const { fps } = useVideoConfig();
const opacity = interpolate(frame, [0, fps], [0, 1], { extrapolateRight: 'clamp' });
```

### Sequences
Use `<Sequence>` to time when elements appear:
```tsx
<Sequence from={30} durationInFrames={60}>
  <Title />
</Sequence>
```

## Rule References

Read these for detailed patterns (loaded from upstream Remotion skills):

| Rule | Description |
|------|-------------|
| `references/animations.md` | Frame-based animation fundamentals |
| `references/timing.md` | Springs, easing, interpolation curves |
| `references/compositions.md` | Defining compositions, stills, folders |
| `references/sequencing.md` | Timing and ordering elements |
| `references/videos.md` | Embedding videos - trim, volume, speed |
| `references/audio.md` | Audio handling - import, trim, volume |
| `references/assets.md` | Images, fonts, static files |
| `references/transitions.md` | Scene transitions |
| `references/text-animations.md` | Typography animation patterns |
| `references/charts.md` | Data visualization patterns |
| `references/display-captions.md` | TikTok-style captions |

## CLI Commands

```bash
# Project management
python3 Skills/remotion/scripts/remotion_cli.py new <name> [--template blank|hello-world]
python3 Skills/remotion/scripts/remotion_cli.py studio <name>
python3 Skills/remotion/scripts/remotion_cli.py render <name> [--composition ID] [--output path]
python3 Skills/remotion/scripts/remotion_cli.py list

# Rendering options
--composition ID    # Specific composition to render (default: first)
--output PATH       # Output file path (default: out/video.mp4)
--fps N             # Override FPS
--width N           # Override width
--height N          # Override height
--codec CODEC       # h264, h265, vp8, vp9, prores (default: h264)
```

## Common Patterns

### Fade In/Out
```tsx
const frame = useCurrentFrame();
const { fps, durationInFrames } = useVideoConfig();

const fadeIn = interpolate(frame, [0, fps], [0, 1], { extrapolateRight: 'clamp' });
const fadeOut = interpolate(frame, [durationInFrames - fps, durationInFrames], [1, 0], { extrapolateLeft: 'clamp' });
const opacity = fadeIn * fadeOut;
```

### Spring Animation (Natural Motion)
```tsx
const scale = spring({
  frame,
  fps,
  config: { damping: 200 }, // Smooth, no bounce
});
```

### Staggered Elements
```tsx
{items.map((item, i) => (
  <Sequence key={i} from={i * 10}>
    <Item data={item} />
  </Sequence>
))}
```

### Data-Driven Video
```tsx
type VideoProps = { title: string; stats: number[] };

export const DataVideo: React.FC<VideoProps> = ({ title, stats }) => {
  // Animate based on props
};

// In Root.tsx:
<Composition
  id="DataVideo"
  component={DataVideo}
  defaultProps={{ title: "Q4 Results", stats: [10, 20, 30] }}
  // ...
/>
```

## Integration with Zo

### Batch Rendering
Use `/zo/ask` to render multiple videos in parallel:
```python
for row in data:
    # Each call renders with different props
    await render_video(row)
```

### Output Location
Projects live in `Sites/<name>/` for consistency with Zo's site system.
Rendered videos output to `Sites/<name>/out/`.

## Constraints

- **No CSS animations** - They won't render correctly
- **No Tailwind animation classes** - Same issue
- **Frame-based only** - All motion from `useCurrentFrame()`
- **CPU-intensive** - Rendering takes time; complex videos = longer render
- **Node.js required** - Remotion needs Node environment (already available in Zo)
