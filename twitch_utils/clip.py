import os
import json
import parselmouth as pm

from subprocess import run, PIPE
from tempfile import NamedTemporaryFile


class Clip(object):
    @staticmethod
    def clip_info(path: str) -> dict:
        command = ('ffprobe -v error -of json -show_entries '
                   'format=duration,start_time ' + path).split()
        proc = run(command, stdout=PIPE)
        return json.loads(proc.stdout)

    def __init__(self, path: str, tmpfile=None):
        self.name = os.path.basename(path)
        self.path = path
        self._tmpfile = tmpfile

        info = self.clip_info(path)['format']
        if 'start_time' in info:  ## MPEG-TS only
            self.start = float(info['start_time'])
        else:
            self.start = 0
        self.duration = float(info['duration'])
        self.end = self.start + self.duration

        self.inpoint = self.start
        self.outpoint = self.end

    def __del__(self):
        if self._tmpfile:
            self._tmpfile.close()

    def slice(self, start: float, duration: float,
              chunks: int = 1, format: str = 'wav'):
        """Split this Clip into one or multiple temporary Clips.

        By default splits only the audio track, outputting chunks
        in WAV format.
        """
        command = (f'ffmpeg -y -v error -ss {start} '
                   f'-i {self.path} -vn').split()

        results = []
        for i in range(chunks):
            tmp = NamedTemporaryFile()
            results.append(tmp)

            if self.duration < start + duration:
                duration = self.duration - start

            output = (f'-f {format} -ss {duration * i} '
                      f'-t {duration} {tmp.name}').split()
            command.extend(output)

        if run(command).returncode != 0:
            [chunk.close() for chunk in results]
            raise Exception('ffmpeg exited with non-zero code')

        return [Clip(chunk.name, tmpfile=chunk) for chunk in results]

    def offset(self, clip: 'Clip') -> (float, float):
        """Find position of this Clip in another Clip (may be negative).
        
        Returns two values: offset in seconds and cross-correlation score.
        """
        s1, s2 = pm.Sound(self.path), pm.Sound(clip.path)
        cc = s1.cross_correlate(s2, pm.AmplitudeScaling.SUM)
        score = cc.values.max()
        frame = cc.values.argmax()
        offset = cc.frame_number_to_time(frame)
        return offset, score
