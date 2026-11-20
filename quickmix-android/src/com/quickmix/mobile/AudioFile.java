package com.quickmix.mobile;

import android.content.Context;
import android.media.*;
import android.net.Uri;
import java.io.*;
import java.nio.*;

final class AudioFile {
    final short[] samples;
    final int rate, channels;
    AudioFile(short[] samples,int rate,int channels) {
        this.samples=samples; this.rate=rate; this.channels=channels;
    }

    static AudioFile read(Context context, Uri uri) throws IOException {
        MediaExtractor extractor=new MediaExtractor();
        MediaCodec decoder=null;
        try {
            extractor.setDataSource(context,uri,null);
            MediaFormat format=null;
            for (int i=0;i<extractor.getTrackCount();i++) {
                MediaFormat candidate=extractor.getTrackFormat(i);
                String mime=candidate.getString(MediaFormat.KEY_MIME);
                if (mime!=null && mime.startsWith("audio/")) {
                    format=candidate;
                    extractor.selectTrack(i);
                    break;
                }
            }
            if (format==null) throw new IOException("没有找到音轨");
            decoder=MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));
            decoder.configure(format,null,null,0);
            decoder.start();
            MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
            ByteArrayOutputStream pcm=new ByteArrayOutputStream();
            byte[] buffer=new byte[8192];
            boolean submitted=false;
            int encoding=AudioFormat.ENCODING_PCM_16BIT;
            int rate=format.getInteger(MediaFormat.KEY_SAMPLE_RATE);
            int channels=format.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
            long last=android.os.SystemClock.elapsedRealtime();
            while (android.os.SystemClock.elapsedRealtime()-last<7000) {
                if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException();
                if (!submitted) {
                    int slot=decoder.dequeueInputBuffer(5000);
                    if (slot>=0) {
                        ByteBuffer input=decoder.getInputBuffer(slot);
                        input.clear();
                        int size=extractor.readSampleData(input,0);
                        if (size<0) {
                            submitted=true;
                            decoder.queueInputBuffer(slot,0,0,0,MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                        } else {
                            decoder.queueInputBuffer(slot,0,size,extractor.getSampleTime(),0);
                            extractor.advance();
                        }
                        last=android.os.SystemClock.elapsedRealtime();
                    }
                }
                int slot=decoder.dequeueOutputBuffer(info,5000);
                if (slot==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    MediaFormat output=decoder.getOutputFormat();
                    rate=output.getInteger(MediaFormat.KEY_SAMPLE_RATE);
                    channels=output.getInteger(MediaFormat.KEY_CHANNEL_COUNT);
                    encoding=output.containsKey(MediaFormat.KEY_PCM_ENCODING)
                        ? output.getInteger(MediaFormat.KEY_PCM_ENCODING) : AudioFormat.ENCODING_PCM_16BIT;
                    if (channels<1 || channels>2) throw new IOException("请选择单声道或立体声音频");
                    if (encoding!=AudioFormat.ENCODING_PCM_16BIT && encoding!=AudioFormat.ENCODING_PCM_FLOAT)
                        throw new IOException("不支持此 PCM 编码");
                } else if (slot>=0) {
                    ByteBuffer output=decoder.getOutputBuffer(slot);
                    if (info.size>0 && output!=null) {
                        if ((long)pcm.size()+info.size>24*1024*1024)
                            throw new IOException("音频太长，请先裁剪后再导入");
                        output.position(info.offset);
                        output.limit(info.offset+info.size);
                        while (output.hasRemaining()) {
                            int size=Math.min(buffer.length,output.remaining());
                            output.get(buffer,0,size);
                            pcm.write(buffer,0,size);
                        }
                    }
                    decoder.releaseOutputBuffer(slot,false);
                    last=android.os.SystemClock.elapsedRealtime();
                    if ((info.flags&MediaCodec.BUFFER_FLAG_END_OF_STREAM)!=0) {
                        if (channels<1 || channels>2 || rate<=0) throw new IOException("音频格式不受支持");
                        ByteBuffer bytes=ByteBuffer.wrap(pcm.toByteArray()).order(ByteOrder.LITTLE_ENDIAN);
                        int sampleSize=encoding==AudioFormat.ENCODING_PCM_FLOAT ? 4 : 2;
                        short[] raw=new short[bytes.remaining()/sampleSize/channels*channels];
                        if (raw.length==0) throw new IOException("音频为空");
                        if (sampleSize==2) bytes.asShortBuffer().get(raw);
                        else for (int i=0;i<raw.length;i++) raw[i]=quantize(bytes.getFloat());
                        return new AudioFile(raw,rate,channels);
                    }
                }
            }
            throw new IOException("解码超时");
        } finally {
            if (decoder!=null) decoder.release();
            extractor.release();
        }
    }

    int frames() { return samples.length/channels; }

    int block(int position,float[] out) {
        int count=Math.min(samples.length-position,out.length);
        for (int i=0;i<count;i++) out[i]=samples[position+i]/32768f;
        return count;
    }

    static short quantize(float x) {
        return (short)Math.round(Math.max(-32768,Math.min(32767,x*32768)));
    }

    void write(OutputStream stream,Mixer.Settings settings) throws IOException {
        Mixer mixer=new Mixer(rate,channels);
        BufferedOutputStream out=new BufferedOutputStream(stream);
        int tailFrames=0;
        for (int i=0;i<6;i++) if (settings.values[12+i*6]>0) tailFrames=rate*3/4;
        int length=(frames()+tailFrames)*channels;
        ByteBuffer header=ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN);
        header.putInt(0x46464952).putInt(36+length*2).putInt(0x45564157);
        header.putInt(0x20746d66).putInt(16).putShort((short)1).putShort((short)channels);
        header.putInt(rate).putInt(rate*channels*2).putShort((short)(channels*2)).putShort((short)16);
        header.putInt(0x61746164).putInt(length*2);
        out.write(header.array());
        float[] block=new float[512*channels];
        for (int pos=0;pos<length;) {
            if (Thread.currentThread().isInterrupted()) throw new InterruptedIOException();
            int count;
            if (pos<samples.length) count=block(pos,block);
            else {
                count=Math.min(block.length,length-pos);
                java.util.Arrays.fill(block,0,count,0f);
            }
            mixer.process(block,count,settings);
            for (int i=0;i<count;i++) {
                int sample=quantize(block[i]);
                out.write(sample&255);
                out.write((sample>>>8)&255);
            }
            pos+=count;
        }
        out.flush();
    }
}
