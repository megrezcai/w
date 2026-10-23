"""Integration and numerical tests, using synthetic projective ground truth.
Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
"""
import ctypes as C
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import cv2
import numpy as np
from surface_text.tracking import track_video, validate_quad
from surface_text.exporting import animations, export_bundle

ROOT = Path(__file__).resolve().parents[1]


def synthetic(path, count=40, occluded=False):
    rng=np.random.default_rng(19)
    texture=rng.integers(30,230,(180,320,3),dtype=np.uint8)
    texture=cv2.GaussianBlur(texture,(3,3),0)
    for y in range(15,180,30):
        for x in range(15,320,30):
            cv2.circle(texture,(x,y),4,(240,240,240),-1)
    plane=np.float32([[0,0],[319,0],[319,179],[0,179]])
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),24,(640,360))
    if not writer.isOpened(): raise RuntimeError('Synthetic test video encoder unavailable')
    quads=[]
    for i in range(count):
        q=np.float32([[95+i*.8,65+i*.18],[510+i*.25,50+i*.5],[520+i*.18,280-i*.25],[85+i*.5,295-i*.2]])
        quads.append(q)
        H=cv2.getPerspectiveTransform(plane,q)
        frame=cv2.warpPerspective(texture,H,(640,360))
        if occluded and 14<=i<26: frame[:]=0
        writer.write(frame)
    writer.release()
    return quads


class TrackingTests(unittest.TestCase):
    def test_known_projective_motion(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'motion.avi';q=synthetic(path)
            t=track_video(path,[dict(frame=0,quad=q[0].tolist())])
            self.assertEqual(t['tracking_lost_frames'],0)
            errors=[np.max(np.linalg.norm(np.array(r['quad'])-expected,axis=1)) for r,expected in zip(t['frames_data'],q)]
            self.assertLess(max(errors),2.0,errors)
            self.assertEqual(t['fps_num'],24)

    def test_loss_hidden_until_manual_correction(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'occlusion.avi';q=synthetic(path,occluded=True)
            t=track_video(path,[dict(frame=0,quad=q[0].tolist()),dict(frame=26,quad=q[26].tolist())])
            self.assertFalse(t['frames_data'][15]['valid'])
            self.assertFalse(t['frames_data'][25]['valid'])
            self.assertTrue(t['frames_data'][26]['valid'])
            self.assertTrue(t['frames_data'][-1]['valid'])
            self.assertIn('15|=0',animations(t)['8'])

    def test_reference_start_and_portable_export(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'source with spaces.avi';q=synthetic(path,count=12)
            t=track_video(path,[dict(frame=4,quad=q[4].tolist())])
            self.assertTrue(all(not r['valid'] for r in t['frames_data'][:4]))
            out=export_bundle(path,t,Path(d)/'export','测试字幕')
            self.assertTrue((out/'source.avi').exists())
            self.assertTrue((out/'title.png').exists())
            self.assertIn('frei0r.surfacepin',(out/'surface-text.mlt').read_text())
            self.assertNotIn(str(Path(d)),(out/'surface-text.mlt').read_text())
            xml=ET.parse(out/'surface-text.mlt')
            transitions=[{p.get('name'):p.text for p in tr.findall('property')} for tr in xml.findall('.//transition')]
            title_blend=next(t for t in transitions if t.get('mlt_service')=='qtblend' and t.get('b_track')=='2')
            self.assertEqual(title_blend['a_track'],'1')
            self.assertEqual(title_blend['disable'],'0')
            with self.assertRaises(ValueError):export_bundle(path,t,out,'do not overwrite')
            fixture=dict(track=t,animations=animations(t))
            # Shared fixture verifies the QML JavaScript importer against Python export.
            (ROOT/'tests'/'generated-fixture.json').write_text(json.dumps(fixture),encoding='utf-8')

    def test_crossed_selection_rejected(self):
        with self.assertRaises(ValueError):validate_quad([[0,0],[100,100],[100,0],[0,100]],640,360,True)


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        plugin = ROOT/'bin'/('windows/surfacepin.dll' if os.name=='nt' else 'linux/surfacepin.so')
        cls.lib=C.CDLL(str(plugin))
        cls.lib.f0r_construct.argtypes=[C.c_uint,C.c_uint];cls.lib.f0r_construct.restype=C.c_void_p
        cls.lib.f0r_destruct.argtypes=[C.c_void_p]
        cls.lib.f0r_set_param_value.argtypes=[C.c_void_p,C.c_void_p,C.c_int]
        cls.lib.f0r_update.argtypes=[C.c_void_p,C.c_double,C.c_void_p,C.c_void_p]

    def run_filter(self,image,quad=None,opacity=1):
        image=np.ascontiguousarray(image)
        h,w=image.shape[:2];s=self.lib.f0r_construct(w,h);self.assertTrue(s)
        try:
            if quad is not None:
                for i,(x,y) in enumerate(quad):
                    for j,value in enumerate((x,y)):
                        p=C.c_double((value/((h-1) if j else (w-1))+1)/3)
                        self.lib.f0r_set_param_value(s,C.byref(p),i*2+j)
            p=C.c_double(opacity);self.lib.f0r_set_param_value(s,C.byref(p),8)
            result=np.zeros_like(image)
            self.lib.f0r_update(s,0,image.ctypes.data,result.ctypes.data)
            return result
        finally:self.lib.f0r_destruct(s)

    def test_identity_is_exact(self):
        img=np.random.default_rng(1).integers(0,256,(96,128,4),dtype=np.uint8);img[:,:,3]=255
        self.assertTrue(np.array_equal(img,self.run_filter(img)))

    def test_projected_landmarks(self):
        h,w=150,200;img=np.zeros((h,w,4),np.uint8)
        points=[(30,30),(160,30),(100,75),(35,120),(165,120)]
        colors=[(255,0,0,255),(0,255,0,255),(0,0,255,255),(255,255,0,255),(255,0,255,255)]
        for p,color in zip(points,colors):cv2.circle(img,p,4,color,-1)
        q=np.float32([[33,10],[170,35],[195,138],[8,125]])
        out=self.run_filter(img,q)
        H=cv2.getPerspectiveTransform(np.float32([[0,0],[w-1,0],[w-1,h-1],[0,h-1]]),q)
        expected=cv2.perspectiveTransform(np.float32(points)[None],H)[0]
        for p,color in zip(expected,colors):
            mask=(np.max(np.abs(out[:,:,:3].astype(int)-np.array(color[:3])),axis=2)<5)&(out[:,:,3]>100)
            y,x=np.where(mask);self.assertGreater(len(x),2)
            self.assertLess(np.linalg.norm([x.mean()-p[0],y.mean()-p[1]]),1.0)

    def test_opacity_and_degenerate_surface(self):
        image=np.full((60,80,4),255,np.uint8)
        self.assertFalse(self.run_filter(image,opacity=0).any())
        self.assertFalse(self.run_filter(image,quad=[[2,2]]*4).any())
        self.assertFalse(self.run_filter(image,quad=[[0,0],[0,50],[70,50],[70,0]]).any())

    def test_alpha_edges_do_not_turn_dark(self):
        img=np.zeros((80,120,4),np.uint8);img[:,40:80,:]=255
        out=self.run_filter(img,quad=[[10,5],[110,12],[117,70],[2,77]])
        partial=(out[:,:,3]>0)&(out[:,:,3]<255)
        self.assertTrue(partial.any())
        self.assertTrue(np.all(out[:,:,:3][partial]==255))


if __name__=='__main__':unittest.main(verbosity=2)
