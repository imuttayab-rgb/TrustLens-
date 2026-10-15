import type { FaceLandmarkerResult } from '@mediapipe/tasks-vision';
import { observePitch } from './face-challenge';

/**
 * When a real ID is held beside the applicant, the small printed portrait can
 * legitimately register as a second face. Guide the *largest* face only; the
 * worker must still review the submitted image. Never call this liveness.
 */
export function observeHolderPitch(result: FaceLandmarkerResult): number | null {
  const faces = result.faceLandmarks;
  const transforms = result.facialTransformationMatrixes;
  if (!faces.length || faces.length > 2 || faces.length !== transforms.length) return null;
  const widths = faces.map((face) => {
    if (!face.length) return 0;
    const xs = face.map((point) => point.x);
    return Math.max(...xs) - Math.min(...xs);
  });
  const index = widths.indexOf(Math.max(...widths));
  if (widths[index]! < 0.17) return null;
  // A card portrait must remain smaller than the holder's face or the camera
  // is too far away to make an interpretable comparison.
  if (widths.length === 2 && Math.min(...widths) > widths[index]! * 0.8) return null;
  return observePitch({
    ...result,
    faceLandmarks: [faces[index]!],
    facialTransformationMatrixes: [transforms[index]!],
  });
}
