"""Standalone local editor, useful before configuring a Telegram bot."""
import argparse
import asyncio
from pathlib import Path
from .editor_pro import render_pro

async def main():
    p=argparse.ArgumentParser(description='Render a real-footage edit with optional soundtrack')
    p.add_argument('--clips',nargs='+',required=True,help='Paths to video files')
    p.add_argument('--music',help='Local permitted audio file')
    p.add_argument('--out',default='my_edit.mp4')
    p.add_argument('--seconds',type=int,default=30)
    p.add_argument('--orientation',choices=['vertical','horizontal'],default='vertical')
    p.add_argument('--style',choices=['cinematic','fast','smooth','documentary'],default='cinematic')
    p.add_argument('--color',choices=['natural','cinematic','vivid','noir','warm','cool'],default='natural')
    p.add_argument('--subtitles',help='Optional SRT subtitles to burn into the video')
    p.add_argument('--music-volume',type=float,default=0.85,help='Soundtrack gain from 0 to 1.5')
    p.add_argument('--shotlist',help='JSON with manually specified clip, start, duration, speed per shot')
    p.add_argument('--music-start',type=float,default=0.0,help='Offset into supplied music (seconds)')
    p.add_argument('--preview',action='store_true',help='Lower-resolution draft render')
    args=p.parse_args()
    paths=[Path(s).resolve() for s in args.clips]
    for file in paths+([Path(args.music).resolve()] if args.music else []):
        if not file.is_file():p.error(f'File not found: {file}')
    if args.subtitles and not Path(args.subtitles).is_file():p.error('Subtitles file not found')
    out=Path(args.out).resolve()
    print('Rendering:',out)
    await render_pro(paths,Path(args.music).resolve() if args.music else None,out,args.seconds,args.orientation,args.style,color=args.color,subtitles=Path(args.subtitles).resolve() if args.subtitles else None,music_volume=args.music_volume,preview=args.preview,shotlist=Path(args.shotlist).resolve() if args.shotlist else None,music_start=args.music_start)
    print('Done:',out, out.stat().st_size,'bytes')

if __name__=='__main__':asyncio.run(main())
