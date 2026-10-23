"""Planar LK/RANSAC tracking with explicit loss and user correction anchors.
Copyright (c) 2026. SPDX-License-Identifier: GPL-3.0-or-later
"""
from fractions import Fraction
from pathlib import Path
import cv2
import numpy as np

cv2.setNumThreads(2)


def video_info(path):
    cap = cv2.VideoCapture(str(path))
    try:
        ok, image = cap.read()
        fps = cap.get(cv2.CAP_PROP_FPS)
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not ok or not 1 <= fps <= 240 or count < 1:
            raise ValueError("无法读取视频，或帧率不在 1–240 范围内。请先在 Shotcut 转为恒定帧率 MP4。")
        sar_n, sar_d = cap.get(cv2.CAP_PROP_SAR_NUM), cap.get(cv2.CAP_PROP_SAR_DEN)
        if sar_n > 0 and sar_d > 0 and abs(sar_n / sar_d - 1) > 0.001:
            raise ValueError("暂不支持非方形像素，请先转换为方形像素视频。")
        rate = Fraction(fps).limit_denominator(1001)
        return dict(width=image.shape[1], height=image.shape[0], frames=count,
                    fps_num=rate.numerator, fps_den=rate.denominator)
    finally:
        cap.release()


def read_frame(path, index):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, index)
        ok, frame = cap.read()
        if not ok:
            raise ValueError(f"无法解码第 {index} 帧。")
        return frame
    finally:
        cap.release()


def validate_quad(points, width, height, selection=False):
    q = np.asarray(points, dtype=np.float32)
    if q.shape != (4, 2) or not np.isfinite(q).all():
        raise ValueError("需要四个有效坐标，顺序为左上、右上、右下、左下。")
    edges = np.roll(q, -1, axis=0) - q
    cross = edges[:, 0] * np.roll(edges[:, 1], -1) - edges[:, 1] * np.roll(edges[:, 0], -1)
    if (cross <= 2).any() or cv2.contourArea(q) < 100:
        raise ValueError("四角不能交叉、折叠或过小，请按左上→右上→右下→左下重新选择。")
    if selection and ((q < 0).any() or (q[:, 0] >= width).any() or (q[:, 1] >= height).any()):
        raise ValueError("选择点必须在画面内。")
    if (q[:, 0] < -(width - 1)).any() or (q[:, 0] > 2 * (width - 1)).any() or (q[:, 1] < -(height - 1)).any() or (q[:, 1] > 2 * (height - 1)).any():
        raise ValueError("平面已过远地离开画面。")
    return q


class PlanarTracker:
    def __init__(self, gray, quad):
        self.quad = quad.astype(np.float32)
        self.reference = gray.copy()
        self.prev = gray.copy()
        self.H = np.eye(3)
        self.points = self._features(gray, quad)
        self.base = self.points.copy()
        if len(self.points) < 16:
            raise ValueError("所选平面特征不足。请把边缘包含进四角，或改选更清晰的参考帧。")
        self.sift = cv2.SIFT_create(nfeatures=1400)
        self.keypoints, self.descriptors = self.sift.detectAndCompute(gray, self._mask(gray, quad))
        self.steps = 0

    @staticmethod
    def _mask(gray, quad):
        mask = np.zeros(gray.shape, np.uint8)
        cv2.fillConvexPoly(mask, np.rint(quad).astype(np.int32), 255)
        # Four pixels around the selected face include its physical edge.
        return cv2.dilate(mask, np.ones((5, 5), np.uint8))

    def _features(self, gray, quad):
        pts = cv2.goodFeaturesToTrack(gray, 450, .003, 4, mask=self._mask(gray, quad), blockSize=5)
        return np.empty((0, 1, 2), np.float32) if pts is None else pts

    def _fit(self, src, dst):
        if len(src) < 12:
            return None
        H, inliers = cv2.findHomography(src, dst, cv2.RANSAC, 2.0, maxIters=2500, confidence=.995)
        if H is None or inliers is None:
            return None
        good = inliers.ravel().astype(bool)
        if good.sum() < 12 or good.mean() < .65:
            return None
        base_points = src.reshape(-1, 2)[good]
        coverage = cv2.contourArea(cv2.convexHull(base_points.astype(np.float32))) / cv2.contourArea(self.quad)
        if coverage < .025:
            return None
        q = cv2.perspectiveTransform(self.quad[None], H)[0]
        try:
            validate_quad(q, self.prev.shape[1], self.prev.shape[0])
        except ValueError:
            return None
        previous_q = cv2.perspectiveTransform(self.quad[None], self.H)[0]
        ratio = cv2.contourArea(q) / max(cv2.contourArea(previous_q), 1)
        if not .65 < ratio < 1.5 or np.max(np.linalg.norm(q - previous_q, axis=1)) > .20 * max(self.prev.shape):
            return None
        return H, good, float(good.mean())

    def update(self, gray):
        if len(self.points) < 12:
            return None, "可跟踪的特征点不足"
        dst, status, _ = cv2.calcOpticalFlowPyrLK(self.prev, gray, self.points, None, winSize=(25, 25), maxLevel=3,
                                                criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 40, .01))
        if dst is None:
            return None, "光流计算失败"
        back, back_status, _ = cv2.calcOpticalFlowPyrLK(gray, self.prev, dst, None, winSize=(25, 25), maxLevel=3)
        if back is None:
            return None, "光流回查失败"
        error = np.linalg.norm(self.points.reshape(-1, 2) - back.reshape(-1, 2), axis=1)
        good = status.ravel().astype(bool) & back_status.ravel().astype(bool) & (error < 1.2)
        src, target = self.base[good], dst[good]
        fit = self._fit(src, target)
        if fit is None:
            return None, "平面匹配置信度不足；请在清晰帧添加修正点"
        H, inliers, score = fit
        self.base, self.points = src[inliers], target[inliers]
        self.steps += 1
        # Periodic reference matching reduces accumulated LK drift without forcing recovery after loss.
        if self.steps % 10 == 0 and self.descriptors is not None:
            q = cv2.perspectiveTransform(self.quad[None], H)[0]
            kp, desc = self.sift.detectAndCompute(gray, self._mask(gray, q))
            if desc is not None and len(desc) >= 2:
                pairs = cv2.BFMatcher().knnMatch(self.descriptors, desc, k=2)
                matches = [a for pair in pairs if len(pair) == 2 for a, b in [pair] if a.distance < .70 * b.distance]
                if len(matches) >= 16:
                    a = np.float32([self.keypoints[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
                    b = np.float32([kp[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
                    anchored = self._fit(a, b)
                    if anchored is not None:
                        candidate = cv2.perspectiveTransform(self.quad[None], anchored[0])[0]
                        if np.max(np.linalg.norm(candidate - q, axis=1)) < 8:
                            H, accepted, score = anchored
                            self.base, self.points = a[accepted], b[accepted]
        self.H, self.prev = H, gray.copy()
        q = cv2.perspectiveTransform(self.quad[None], H)[0]
        if len(self.points) < 100:
            new = self._features(gray, q)
            if len(new) >= 16:
                self.points = new
                self.base = cv2.perspectiveTransform(new, np.linalg.inv(H)).astype(np.float32)
        return (q, score), None


def track_video(path, anchors, progress=None, cancelled=None, max_width=1280):
    info = video_info(path)
    anchors = sorted(anchors, key=lambda a: int(a['frame']))
    if not anchors or len({int(a['frame']) for a in anchors}) != len(anchors):
        raise ValueError("至少需要一个参考帧，同一帧不能有重复修正点。")
    normalized = {}
    for a in anchors:
        f = int(a['frame'])
        if not 0 <= f < info['frames']:
            raise ValueError("参考帧超出视频范围。")
        normalized[f] = validate_quad(a['quad'], info['width'], info['height'], selection=True)
    scale = min(1., max_width / info['width'])
    results = []
    tracker = None
    cap = cv2.VideoCapture(str(path))
    try:
        for frame_index in range(info['frames']):
            if cancelled and cancelled():
                raise InterruptedError("操作已取消。")
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f"第 {frame_index} 帧解码失败，未输出不完整的跟踪结果。")
            small = cv2.resize(frame, None, fx=scale, fy=scale) if scale < 1 else frame
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            record = dict(frame=frame_index, valid=False, quad=None, score=0., reason="参考帧之前")
            if frame_index in normalized:
                q = normalized[frame_index]
                tracker = PlanarTracker(gray, q * scale)
                record.update(valid=True, quad=q.tolist(), score=1., reason="手动参考帧")
            elif tracker is not None:
                value, reason = tracker.update(gray)
                if value is None:
                    tracker = None
                    record['reason'] = reason
                else:
                    q, score = value
                    record.update(valid=True, quad=(q / scale).tolist(), score=score, reason="自动跟踪")
            elif frame_index > anchors[0]['frame']:
                record['reason'] = "跟踪丢失，等待手动修正点"
            results.append(record)
            if progress and (frame_index % 4 == 0 or frame_index + 1 == info['frames']):
                progress(frame_index + 1, info['frames'])
    finally:
        cap.release()
    return dict(schema='shotcut-surface-text/v1', **info, anchors=anchors, frames_data=results,
                source_name=Path(path).name, lost_frames=sum(not r['valid'] for r in results),
                tracking_lost_frames=sum(not r['valid'] and r['frame'] >= anchors[0]['frame'] for r in results))
