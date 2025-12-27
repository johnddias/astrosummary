"""
Subframe Quality Analyzer

Computes objective quality metrics for astrophotography sub-frames.
Focuses on metrics relevant to PixInsight WBPP rejection validation.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
from astropy.io import fits
from scipy import ndimage
from scipy.optimize import curve_fit
import logging

logger = logging.getLogger("backend.quality_analyzer")


@dataclass
class QualityMetrics:
    """Quality metrics for a single sub-frame"""
    snr: float                    # Signal-to-noise ratio
    fwhm: float                   # Full-width half-maximum (pixels)
    eccentricity: float           # Star elongation (0=round, 1=linear)
    star_count: int               # Number of detected stars
    background_median: float      # Sky background level
    background_std: float         # Background noise
    gradient_strength: float      # Background gradient magnitude
    quality_score: float          # Composite quality score (0-1)
    phd2_rms: Optional[float] = None  # Optional PHD2 guiding RMS

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'snr': float(self.snr),
            'fwhm': float(self.fwhm),
            'eccentricity': float(self.eccentricity),
            'star_count': int(self.star_count),
            'background_median': float(self.background_median),
            'background_std': float(self.background_std),
            'gradient_strength': float(self.gradient_strength),
            'quality_score': float(self.quality_score),
            'phd2_rms': float(self.phd2_rms) if self.phd2_rms is not None else None
        }


class SubframeAnalyzer:
    """Analyzes FITS sub-frames for quality metrics"""

    def __init__(self, star_detection_threshold: float = 5.0, fast_mode: bool = True):
        """
        Initialize analyzer

        Args:
            star_detection_threshold: Sigma threshold for star detection
            fast_mode: If True, use fast analysis (center crop, no star detection)
        """
        self.star_threshold = star_detection_threshold
        self.fast_mode = fast_mode

    def analyze_frame(self, fits_path: str, max_size: int = 1000) -> QualityMetrics:
        """Analyze a FITS file - delegates to fast or full analysis"""
        if self.fast_mode:
            return self._analyze_frame_fast(fits_path)
        else:
            return self._analyze_frame_full(fits_path, max_size)

    def _analyze_frame_fast(self, fits_path: str) -> QualityMetrics:
        """
        Fast analysis - only loads center crop and computes basic stats.
        Much faster (~0.5s per frame) but less accurate.
        """
        try:
            # Helper to load center crop from FITS
            def load_center_crop(use_memmap: bool):
                with fits.open(fits_path, memmap=use_memmap) as hdul:
                    if hdul[0].data is None:
                        raise ValueError("No image data")

                    # Get image shape
                    shape = hdul[0].data.shape
                    if len(shape) != 2:
                        raise ValueError(f"Expected 2D, got {shape}")

                    h, w = shape

                    # Extract a 500x500 center crop for analysis
                    crop_size = min(500, h, w)
                    y_start = (h - crop_size) // 2
                    x_start = (w - crop_size) // 2

                    # Load just the center crop
                    return hdul[0].data[y_start:y_start+crop_size, x_start:x_start+crop_size].astype(np.float32)

            # Try with memmap first for speed, fall back if BZERO/BSCALE/BLANK present
            try:
                crop = load_center_crop(use_memmap=True)
            except (ValueError, OSError) as e:
                if 'memmap' in str(e).lower() or 'BZERO' in str(e) or 'BSCALE' in str(e) or 'BLANK' in str(e):
                    crop = load_center_crop(use_memmap=False)
                else:
                    raise

            # Simple background stats
            bg_median = float(np.median(crop))
            # Use MAD for robust noise estimate
            mad = float(np.median(np.abs(crop - bg_median))) * 1.4826

            # Simple SNR: ratio of signal range to noise
            signal_range = float(np.percentile(crop, 99) - np.percentile(crop, 1))
            snr = signal_range / max(mad, 1.0)

            # Estimate star count from bright pixels
            threshold = bg_median + 5 * mad
            bright_pixels = np.sum(crop > threshold)
            # Rough estimate: assume average star is ~20 pixels
            star_count = max(0, bright_pixels // 20)

            # Simple gradient check (crop is square, so use shape[0])
            half = crop.shape[0] // 2
            top_half = np.mean(crop[:half, :])
            bottom_half = np.mean(crop[half:, :])
            gradient = abs(top_half - bottom_half) / max(bg_median, 1.0)
            gradient = min(gradient, 1.0)

            # Compute quality score
            snr_norm = min(snr / 50.0, 1.0)
            star_norm = min(star_count / 50.0, 1.0)
            grad_norm = 1.0 - gradient

            quality_score = 0.5 * snr_norm + 0.3 * star_norm + 0.2 * grad_norm

            return QualityMetrics(
                snr=snr,
                fwhm=0.0,  # Not computed in fast mode
                eccentricity=0.0,  # Not computed in fast mode
                star_count=int(star_count),
                background_median=bg_median,
                background_std=mad,
                gradient_strength=gradient,
                quality_score=float(quality_score)
            )

        except Exception as e:
            logger.error(f"Fast analysis error for {fits_path}: {e}")
            return QualityMetrics(
                snr=0.0, fwhm=0.0, eccentricity=1.0, star_count=0,
                background_median=0.0, background_std=0.0,
                gradient_strength=1.0, quality_score=0.0
            )

    def _analyze_frame_full(self, fits_path: str, max_size: int = 1000) -> QualityMetrics:
        """
        Analyze a FITS file and compute quality metrics

        Args:
            fits_path: Path to FITS file
            max_size: Maximum dimension for analysis (images are downsampled for speed)

        Returns:
            QualityMetrics object with all computed metrics
        """
        try:
            # Try with memmap first, fall back to non-memmap if needed
            try:
                with fits.open(fits_path, memmap=True) as hdul:
                    image_data = hdul[0].data
                    if image_data is None:
                        raise ValueError("FITS file has no image data in primary HDU")
                    image_data = image_data.astype(np.float32)
            except (ValueError, OSError) as e:
                # BZERO/BSCALE/BLANK keywords prevent memmap, use regular reading
                if 'memmap' in str(e).lower() or 'BZERO' in str(e):
                    with fits.open(fits_path, memmap=False) as hdul:
                        image_data = hdul[0].data
                        if image_data is None:
                            raise ValueError("FITS file has no image data in primary HDU")
                        image_data = image_data.astype(np.float32)
                else:
                    raise

            # Validate image data shape
            if len(image_data.shape) != 2:
                raise ValueError(f"Expected 2D image, got shape {image_data.shape}")

            # Downsample large images for faster processing
            original_shape = image_data.shape
            downsample_factor = 1
            if max(image_data.shape) > max_size:
                downsample_factor = max(image_data.shape) // max_size
                # Use simple slicing for fast downsampling
                image_data = image_data[::downsample_factor, ::downsample_factor]

            # Compute background statistics
            bg_median, bg_std = self._estimate_background(image_data)

            # Detect stars
            star_positions = self._detect_stars(image_data, bg_median, bg_std)
            star_count = len(star_positions)

            # Compute star-based metrics
            if star_count > 0:
                fwhm = self._compute_fwhm(image_data, star_positions, bg_median)
                # Scale FWHM back to original resolution
                fwhm = fwhm * downsample_factor
                eccentricity = self._compute_eccentricity(image_data, star_positions, bg_median)
                signal = self._compute_signal(image_data, star_positions, bg_median)
                # Scale star count estimate to original resolution
                star_count = int(star_count * (downsample_factor ** 2))
            else:
                # No stars detected - likely cloudy or poor quality
                fwhm = 0.0
                eccentricity = 1.0  # Worst eccentricity
                signal = bg_median

            # Compute SNR
            snr = self._compute_snr(signal, bg_median, bg_std)

            # Compute gradient
            gradient = self._compute_gradient(image_data, bg_median)

            # Compute composite quality score
            quality_score = self._compute_quality_score(
                snr, fwhm, eccentricity, star_count, gradient
            )

            return QualityMetrics(
                snr=snr,
                fwhm=fwhm,
                eccentricity=eccentricity,
                star_count=star_count,
                background_median=bg_median,
                background_std=bg_std,
                gradient_strength=gradient,
                quality_score=quality_score
            )

        except Exception as e:
            import traceback
            logger.error(f"Error analyzing {fits_path}: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            # Return worst-case metrics on error
            return QualityMetrics(
                snr=0.0, fwhm=0.0, eccentricity=1.0, star_count=0,
                background_median=0.0, background_std=0.0,
                gradient_strength=1.0, quality_score=0.0
            )

    def _estimate_background(self, image: np.ndarray) -> Tuple[float, float]:
        """
        Estimate background level and noise using robust statistics

        Uses median and MAD (median absolute deviation) on bottom 50% of pixels
        """
        # Use bottom 50th percentile as background sample
        bg_sample = image[image < np.percentile(image, 50)]

        median = np.median(bg_sample)
        # MAD = median(|x - median|) * 1.4826 (for Gaussian distribution)
        mad = np.median(np.abs(bg_sample - median)) * 1.4826

        return float(median), float(mad)

    def _detect_stars(
        self,
        image: np.ndarray,
        bg_median: float,
        bg_std: float
    ) -> List[Tuple[int, int]]:
        """
        Detect stars using simple thresholding and connected components

        Returns list of (y, x) positions of detected stars
        """
        # Threshold at N sigma above background
        threshold = bg_median + self.star_threshold * bg_std
        binary = image > threshold

        # Label connected components
        labeled, num_features = ndimage.label(binary)

        # Find centroids of components
        star_positions = []
        for i in range(1, num_features + 1):
            y, x = ndimage.center_of_mass(image, labeled, i)

            # Filter out edge detections and very small objects
            if (10 < y < image.shape[0] - 10 and
                10 < x < image.shape[1] - 10):
                star_positions.append((int(y), int(x)))

        return star_positions

    def _compute_fwhm(
        self,
        image: np.ndarray,
        star_positions: List[Tuple[int, int]],
        bg_median: float,
        box_size: int = 15
    ) -> float:
        """
        Compute mean FWHM of detected stars

        Uses Gaussian fitting on brightest stars
        """
        if not star_positions:
            return 0.0

        fwhms = []

        # Sort stars by brightness, take top 20 or all if fewer
        star_brightnesses = [
            (image[y, x], y, x) for y, x in star_positions
        ]
        star_brightnesses.sort(reverse=True)
        top_stars = star_brightnesses[:min(20, len(star_brightnesses))]

        for brightness, y, x in top_stars:
            # Extract cutout around star
            half_box = box_size // 2
            y0, y1 = max(0, y - half_box), min(image.shape[0], y + half_box + 1)
            x0, x1 = max(0, x - half_box), min(image.shape[1], x + half_box + 1)

            cutout = image[y0:y1, x0:x1] - bg_median

            # Simple FWHM estimation using radial profile
            cy, cx = cutout.shape[0] // 2, cutout.shape[1] // 2

            # Create radial distance array
            yy, xx = np.ogrid[:cutout.shape[0], :cutout.shape[1]]
            r = np.sqrt((yy - cy)**2 + (xx - cx)**2)

            # Find radius at half maximum
            max_val = cutout[cy, cx]
            if max_val > 0:
                half_max = max_val / 2.0
                # Find pixels close to half maximum
                half_max_mask = np.abs(cutout - half_max) < (max_val * 0.1)
                if np.any(half_max_mask):
                    half_max_radius = np.mean(r[half_max_mask])
                    fwhm = 2.0 * half_max_radius
                    if 0.5 < fwhm < 20.0:  # Sanity check
                        fwhms.append(fwhm)

        return float(np.median(fwhms)) if fwhms else 0.0

    def _compute_eccentricity(
        self,
        image: np.ndarray,
        star_positions: List[Tuple[int, int]],
        bg_median: float,
        box_size: int = 15
    ) -> float:
        """
        Compute mean eccentricity of detected stars using image moments

        Eccentricity = 1 - (minor_axis / major_axis)
        0 = perfectly round, 1 = linear
        """
        if not star_positions:
            return 1.0

        eccentricities = []

        for y, x in star_positions[:20]:  # Use top 20 stars
            half_box = box_size // 2
            y0, y1 = max(0, y - half_box), min(image.shape[0], y + half_box + 1)
            x0, x1 = max(0, x - half_box), min(image.shape[1], x + half_box + 1)

            cutout = image[y0:y1, x0:x1] - bg_median
            cutout[cutout < 0] = 0

            # Compute second moments
            yy, xx = np.ogrid[:cutout.shape[0], :cutout.shape[1]]
            cy, cx = ndimage.center_of_mass(cutout)

            if np.sum(cutout) > 0:
                # Compute moment matrix
                Mxx = np.sum(cutout * (xx - cx)**2) / np.sum(cutout)
                Myy = np.sum(cutout * (yy - cy)**2) / np.sum(cutout)
                Mxy = np.sum(cutout * (xx - cx) * (yy - cy)) / np.sum(cutout)

                # Eigenvalues give major/minor axis lengths
                trace = Mxx + Myy
                det = Mxx * Myy - Mxy**2

                if trace > 0 and det > 0:
                    lambda1 = (trace + np.sqrt(trace**2 - 4*det)) / 2
                    lambda2 = (trace - np.sqrt(trace**2 - 4*det)) / 2

                    if lambda1 > 0 and lambda2 > 0:
                        eccentricity = 1.0 - np.sqrt(lambda2 / lambda1)
                        if 0 <= eccentricity <= 1:
                            eccentricities.append(eccentricity)

        return float(np.median(eccentricities)) if eccentricities else 0.5

    def _compute_signal(
        self,
        image: np.ndarray,
        star_positions: List[Tuple[int, int]],
        bg_median: float
    ) -> float:
        """Compute median signal level from brightest stars"""
        if not star_positions:
            return bg_median

        star_values = [image[y, x] for y, x in star_positions]
        star_values.sort(reverse=True)
        top_stars = star_values[:min(10, len(star_values))]

        return float(np.median(top_stars))

    def _compute_snr(self, signal: float, bg_median: float, bg_std: float) -> float:
        """Compute signal-to-noise ratio"""
        if bg_std == 0:
            return 0.0

        net_signal = signal - bg_median
        return float(max(0.0, net_signal / bg_std))

    def _compute_gradient(self, image: np.ndarray, bg_median: float) -> float:
        """
        Compute background gradient strength

        Fits a 2D plane to the image and measures tilt magnitude
        """
        # Downsample for speed
        small = image[::4, ::4]

        # Create coordinate grids
        h, w = small.shape
        yy, xx = np.mgrid[0:h, 0:w]

        # Fit plane: z = ax + by + c
        coords = np.stack([xx.ravel(), yy.ravel(), np.ones(xx.size)]).T
        values = small.ravel()

        try:
            # Least squares fit
            coeffs, _, _, _ = np.linalg.lstsq(coords, values, rcond=None)
            a, b, c = coeffs

            # Gradient magnitude normalized by background
            gradient_mag = np.sqrt(a**2 + b**2)
            normalized_gradient = gradient_mag / max(bg_median, 1.0)

            return float(min(normalized_gradient, 1.0))
        except:
            return 0.0

    def _compute_quality_score(
        self,
        snr: float,
        fwhm: float,
        eccentricity: float,
        star_count: int,
        gradient: float
    ) -> float:
        """
        Compute composite quality score (0-1)

        Weighted combination of normalized metrics
        """
        # Normalize metrics to 0-1 range (using empirical thresholds)
        snr_norm = min(snr / 20.0, 1.0)  # SNR of 20 = excellent
        fwhm_norm = max(0.0, 1.0 - fwhm / 6.0) if fwhm > 0 else 0.0  # FWHM of 6 = poor
        ecc_norm = 1.0 - eccentricity  # Lower eccentricity = better
        star_norm = min(star_count / 100.0, 1.0)  # 100 stars = good
        grad_norm = 1.0 - gradient  # Lower gradient = better

        # Weighted combination
        score = (
            0.35 * snr_norm +
            0.25 * fwhm_norm +
            0.20 * ecc_norm +
            0.10 * star_norm +
            0.10 * grad_norm
        )

        return float(max(0.0, min(1.0, score)))
