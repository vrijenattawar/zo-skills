#!/usr/bin/env python3
"""
Remotion CLI for Zo
Scaffold, preview, and render Remotion video projects.

Usage:
    python3 Skills/remotion/scripts/remotion_cli.py new <name> [--template blank|hello-world]
    python3 Skills/remotion/scripts/remotion_cli.py studio <name>
    python3 Skills/remotion/scripts/remotion_cli.py render <name> [options]
    python3 Skills/remotion/scripts/remotion_cli.py list
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path("/home/workspace")
SITES_DIR = WORKSPACE / "Sites"
SKILL_DIR = WORKSPACE / "Skills" / "remotion"

# Blank template - minimal starting point
BLANK_TEMPLATE = {
    "package.json": """{
  "name": "{name}",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "studio": "remotion studio",
    "render": "remotion render",
    "build": "remotion bundle"
  },
  "dependencies": {
    "@remotion/cli": "^4.0.0",
    "@remotion/player": "^4.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "remotion": "^4.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.0.0",
    "typescript": "^5.0.0"
  }
}""",
    "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "declaration": true,
    "declarationMap": true,
    "noEmit": true
  },
  "include": ["src/**/*"]
}""",
    "src/index.ts": """import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
""",
    "src/Root.tsx": """import { Composition } from "remotion";
import { MyComposition } from "./Composition";

export const RemotionRoot = () => {
  return (
    <Composition
      id="MyVideo"
      component={MyComposition}
      durationInFrames={150}
      fps={30}
      width={1920}
      height={1080}
      defaultProps={{
        title: "Hello from Zo!",
      }}
    />
  );
};
""",
    "src/Composition.tsx": """import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

type Props = {
  title: string;
};

export const MyComposition: React.FC<Props> = ({ title }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  // Fade in over 1 second
  const opacity = interpolate(frame, [0, fps], [0, 1], {
    extrapolateRight: "clamp",
  });

  // Spring scale animation
  const scale = spring({
    frame,
    fps,
    config: { damping: 200 },
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0f0f0f",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          color: "white",
          fontSize: 80,
          fontWeight: "bold",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        {title}
      </div>
    </AbsoluteFill>
  );
};
""",
}


def get_project_dir(name: str) -> Path:
    """Get the project directory for a Remotion project."""
    return SITES_DIR / name


def list_projects() -> list[str]:
    """List all Remotion projects."""
    projects = []
    if SITES_DIR.exists():
        for d in SITES_DIR.iterdir():
            if d.is_dir():
                pkg = d / "package.json"
                if pkg.exists():
                    try:
                        data = json.loads(pkg.read_text())
                        deps = data.get("dependencies", {})
                        if "remotion" in deps or "@remotion/cli" in deps:
                            projects.append(d.name)
                    except:
                        pass
    return sorted(projects)


def cmd_new(args):
    """Create a new Remotion project."""
    name = args.name
    template = args.template or "blank"
    
    project_dir = get_project_dir(name)
    
    if project_dir.exists():
        print(f"❌ Project already exists: {project_dir}")
        sys.exit(1)
    
    print(f"📦 Creating Remotion project: {name}")
    
    # Create directories
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "src").mkdir(exist_ok=True)
    (project_dir / "public").mkdir(exist_ok=True)
    (project_dir / "out").mkdir(exist_ok=True)
    
    # Write template files
    if template == "blank":
        for filename, content in BLANK_TEMPLATE.items():
            filepath = project_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content.replace("{name}", name))
            print(f"  ✓ Created {filename}")
    else:
        # Use bun create video for official templates
        print(f"  Using official template: {template}")
        result = subprocess.run(
            ["bunx", "create-video@latest", name, "--template", template],
            cwd=SITES_DIR,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            print(f"❌ Failed to create project: {result.stderr}")
            sys.exit(1)
    
    # Install dependencies
    print(f"\n📥 Installing dependencies...")
    result = subprocess.run(
        ["bun", "install"],
        cwd=project_dir,
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f"⚠️  Dependency installation had issues: {result.stderr}")
    else:
        print("  ✓ Dependencies installed")
    
    print(f"\n✅ Project created at: {project_dir}")
    print(f"\nNext steps:")
    print(f"  1. Edit src/Composition.tsx to build your video")
    print(f"  2. Preview: python3 Skills/remotion/scripts/remotion_cli.py studio {name}")
    print(f"  3. Render: python3 Skills/remotion/scripts/remotion_cli.py render {name}")


def cmd_studio(args):
    """Start the Remotion studio for a project."""
    name = args.name
    project_dir = get_project_dir(name)
    
    if not project_dir.exists():
        print(f"❌ Project not found: {name}")
        print(f"   Available projects: {', '.join(list_projects()) or 'none'}")
        sys.exit(1)
    
    port = args.port or 3000
    
    print(f"🎬 Starting Remotion Studio for {name} on port {port}...")
    print(f"   Preview at: http://localhost:{port}")
    
    # Run in foreground so user can see output
    subprocess.run(
        ["bunx", "remotion", "studio", "--port", str(port)],
        cwd=project_dir
    )


def cmd_render(args):
    """Render a Remotion project to video."""
    name = args.name
    project_dir = get_project_dir(name)
    
    if not project_dir.exists():
        print(f"❌ Project not found: {name}")
        print(f"   Available projects: {', '.join(list_projects()) or 'none'}")
        sys.exit(1)
    
    # Build render command
    composition = args.composition or "MyVideo"
    output = args.output or f"out/{composition}.mp4"
    
    cmd = ["bunx", "remotion", "render", composition, output]
    
    if args.codec:
        cmd.extend(["--codec", args.codec])
    if args.fps:
        cmd.extend(["--fps", str(args.fps)])
    if args.width:
        cmd.extend(["--width", str(args.width)])
    if args.height:
        cmd.extend(["--height", str(args.height)])
    if args.props:
        cmd.extend(["--props", args.props])
    
    print(f"🎬 Rendering {composition} from {name}...")
    print(f"   Output: {project_dir / output}")
    
    result = subprocess.run(cmd, cwd=project_dir)
    
    if result.returncode == 0:
        output_path = project_dir / output
        print(f"\n✅ Render complete: {output_path}")
        return str(output_path)
    else:
        print(f"\n❌ Render failed with code {result.returncode}")
        sys.exit(1)


def cmd_list(args):
    """List all Remotion projects."""
    projects = list_projects()
    
    if not projects:
        print("No Remotion projects found.")
        print(f"Create one with: python3 Skills/remotion/scripts/remotion_cli.py new <name>")
        return
    
    print("Remotion projects:")
    for p in projects:
        project_dir = get_project_dir(p)
        has_out = (project_dir / "out").exists() and any((project_dir / "out").iterdir()) if (project_dir / "out").exists() else False
        status = "✓ has renders" if has_out else ""
        print(f"  • {p} {status}")


def main():
    parser = argparse.ArgumentParser(
        description="Remotion CLI for Zo - Create videos programmatically",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # new
    new_parser = subparsers.add_parser("new", help="Create a new Remotion project")
    new_parser.add_argument("name", help="Project name")
    new_parser.add_argument("--template", "-t", default="blank", 
                           help="Template: blank (default), hello-world, or official template name")
    new_parser.set_defaults(func=cmd_new)
    
    # studio
    studio_parser = subparsers.add_parser("studio", help="Start Remotion Studio")
    studio_parser.add_argument("name", help="Project name")
    studio_parser.add_argument("--port", "-p", type=int, default=3000, help="Port number")
    studio_parser.set_defaults(func=cmd_studio)
    
    # render
    render_parser = subparsers.add_parser("render", help="Render video")
    render_parser.add_argument("name", help="Project name")
    render_parser.add_argument("--composition", "-c", help="Composition ID to render")
    render_parser.add_argument("--output", "-o", help="Output file path")
    render_parser.add_argument("--codec", help="Video codec: h264, h265, vp8, vp9, prores")
    render_parser.add_argument("--fps", type=int, help="Override FPS")
    render_parser.add_argument("--width", type=int, help="Override width")
    render_parser.add_argument("--height", type=int, help="Override height")
    render_parser.add_argument("--props", help="JSON props to pass to composition")
    render_parser.set_defaults(func=cmd_render)
    
    # list
    list_parser = subparsers.add_parser("list", help="List Remotion projects")
    list_parser.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    args.func(args)


if __name__ == "__main__":
    main()
