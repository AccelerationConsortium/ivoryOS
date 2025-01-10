import cv2
import numpy as np


class ColorAnalyzer:
    def __init__(self, reference_image_path, roi_coords):
        self.reference_image = self.load_image(reference_image_path)
        self.roi_coords = roi_coords
        self.reference_lab = self.convert_to_lab(self.reference_image)
        self.reference_roi = self.get_roi(self.reference_lab)
        self.reference_color = self.calculate_average_color(self.reference_roi)

    def load_image(self, path):
        # Load an image in BGR color space
        return cv2.imread(path)

    def convert_to_lab(self, image):
        # Convert from BGR to Lab color space
        return cv2.cvtColor(image, cv2.COLOR_BGR2Lab)

    def get_roi(self, image):
        # Extract the Region of Interest
        x, y, width, height = self.roi_coords
        cv2.imwrite("test.png", image[y:y + height, x:x + width])
        return image[y:y + height, x:x + width]

    def calculate_average_color(self, roi):
        # Calculate the average color of the ROI
        average_color = np.mean(roi.reshape(-1, roi.shape[-1]), axis=0)
        return average_color

    def color_difference(self, color1, color2):
        # Compute the Euclidean distance between two colors
        return np.linalg.norm(color1 - color2)

    def analyze_image(self, image):
        image_lab = self.convert_to_lab(image)
        image_roi = self.get_roi(image_lab)
        image_color = self.calculate_average_color(image_roi)

        score = self.color_difference(self.reference_color, image_color)
        return score

    def _analyze_image(self, image_path):
        image = self.load_image(image_path)
        return self.analyze_image(image)


if __name__ == "__main__":
    # Example usage:
    reference_image_path = "blue 750ul red 750ul.png"
    roi_coords = (1150, 650, 400, 400)  # Adjust these coordinates to match your ROI
    analyzer = ColorAnalyzer(reference_image_path, roi_coords)

    """
    b0      r1500       90
    b500    r1000       42
    b750    r750        0
    b1000   r500        34
    b1500   r0          114
    """
    # Analyze a new image
    image_path = "blue 0ul red 1500ul.png"

    score = analyzer._analyze_image(image_path)
    print(f"Color difference score: {score}")
