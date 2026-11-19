"""Metrics for comparing visible-person detections with manually labelled boxes."""
from dataclasses import dataclass
from typing import Iterable, Sequence


Box = Sequence[float]


def intersection_over_union(first: Box, second: Box) -> float:
    """Return xyxy box IoU, treating non-positive boxes as non-matches."""
    first_x1, first_y1, first_x2, first_y2 = first
    second_x1, second_y1, second_x2, second_y2 = second
    intersection_width = max(0., min(first_x2, second_x2) - max(first_x1, second_x1))
    intersection_height = max(0., min(first_y2, second_y2) - max(first_y1, second_y1))
    intersection = intersection_width * intersection_height
    first_area = max(0., first_x2 - first_x1) * max(0., first_y2 - first_y1)
    second_area = max(0., second_x2 - second_x1) * max(0., second_y2 - second_y1)
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.


@dataclass
class DetectionMetrics:
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    absolute_count_error: int = 0
    image_count: int = 0

    @property
    def precision(self) -> float:
        denominator = self.true_positives + self.false_positives
        return self.true_positives / denominator if denominator else 0.

    @property
    def recall(self) -> float:
        denominator = self.true_positives + self.false_negatives
        return self.true_positives / denominator if denominator else 0.

    @property
    def f1(self) -> float:
        denominator = self.precision + self.recall
        return 2 * self.precision * self.recall / denominator if denominator else 0.

    @property
    def count_mae(self) -> float:
        return self.absolute_count_error / self.image_count if self.image_count else 0.

    def add_image(
        self,
        predicted_boxes: Iterable[Box],
        labelled_boxes: Iterable[Box],
        iou_threshold: float = .5,
    ) -> None:
        predicted = [tuple(map(float, box)) for box in predicted_boxes]
        labelled = [tuple(map(float, box)) for box in labelled_boxes]
        overlaps = [
            sorted(
                (
                    (intersection_over_union(pred_box, label_box), label_index)
                    for label_index, label_box in enumerate(labelled)
                ),
                reverse=True,
            )
            for pred_box in predicted
        ]
        label_to_prediction: dict[int, int] = {}

        def find_match(prediction_index: int, seen_labels: set[int]) -> bool:
            for overlap, label_index in overlaps[prediction_index]:
                if overlap < iou_threshold:
                    break
                if label_index in seen_labels:
                    continue
                seen_labels.add(label_index)
                previous = label_to_prediction.get(label_index)
                if previous is None or find_match(previous, seen_labels):
                    label_to_prediction[label_index] = prediction_index
                    return True
            return False

        matched_predictions = {
            prediction_index
            for prediction_index in range(len(predicted))
            if find_match(prediction_index, set())
        }
        matched_labels = set(label_to_prediction)

        self.true_positives += len(matched_predictions)
        self.false_positives += len(predicted) - len(matched_predictions)
        self.false_negatives += len(labelled) - len(matched_labels)
        self.absolute_count_error += abs(len(predicted) - len(labelled))
        self.image_count += 1

    def as_dict(self) -> dict[str, int | float]:
        return {
            "images": self.image_count,
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "count_mae": self.count_mae,
        }
