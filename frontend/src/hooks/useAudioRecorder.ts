import { useCallback, useEffect, useRef, useState } from "react";

interface RecorderControls {
  isRecording: boolean;
  start: () => Promise<void>;
  stop: () => Promise<Blob | null>;
  error?: string;
}

export function useAudioRecorder(): RecorderControls {
  const mediaStream = useRef<MediaStream | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [error, setError] = useState<string | undefined>(undefined);

  useEffect(() => {
    return () => {
      recorder.current?.stop();
      mediaStream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const start = useCallback(async () => {
    setError(undefined);
    if (isRecording) {
      return;
    }

    try {
      mediaStream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      recorder.current = new MediaRecorder(mediaStream.current, { mimeType: "audio/webm" });
    } catch (err) {
      setError("Microphone access denied or unsupported browser.");
      throw err;
    }

    chunks.current = [];
    recorder.current!.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) {
        chunks.current.push(event.data);
      }
    });

    recorder.current!.start();
    setIsRecording(true);
  }, [isRecording]);

  const stop = useCallback(async () => {
    if (!isRecording || !recorder.current) {
      return null;
    }

    return await new Promise<Blob | null>((resolve) => {
      const handleStop = () => {
        recorder.current?.removeEventListener("stop", handleStop);
        const blob = chunks.current.length ? new Blob(chunks.current, { type: "audio/webm" }) : null;
        chunks.current = [];
        mediaStream.current?.getTracks().forEach((track) => track.stop());
        mediaStream.current = null;
        recorder.current = null;
        setIsRecording(false);
        resolve(blob);
      };

      recorder.current!.addEventListener("stop", handleStop);
      recorder.current!.stop();
    });
  }, [isRecording]);

  return { isRecording, start, stop, error };
}
