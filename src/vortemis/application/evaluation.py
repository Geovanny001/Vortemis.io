import numpy


def binary_metrics(
    labels: numpy.ndarray,
    predictions: numpy.ndarray,
) -> dict[str, float]:
    truth = numpy.asarray(labels, dtype=bool)
    predicted = numpy.asarray(predictions, dtype=bool)
    true_positive = int(numpy.sum(truth & predicted))
    false_positive = int(numpy.sum(~truth & predicted))
    true_negative = int(numpy.sum(~truth & ~predicted))
    false_negative = int(numpy.sum(truth & ~predicted))
    total = true_positive + false_positive + true_negative + false_negative
    precision = _safe_ratio(true_positive, true_positive + false_positive)
    recall = _safe_ratio(true_positive, true_positive + false_negative)
    f1 = _safe_ratio(2 * precision * recall, precision + recall)
    accuracy = _safe_ratio(true_positive + true_negative, total)
    false_positive_rate = _safe_ratio(false_positive, false_positive + true_negative)
    false_negative_rate = _safe_ratio(false_negative, false_negative + true_positive)
    return {
        "true_positive": float(true_positive),
        "false_positive": float(false_positive),
        "true_negative": float(true_negative),
        "false_negative": float(false_negative),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "false_positive_rate": false_positive_rate,
        "false_negative_rate": false_negative_rate,
    }


def roc_auc(labels: numpy.ndarray, scores: numpy.ndarray) -> float:
    truth = numpy.asarray(labels, dtype=bool)
    values = numpy.asarray(scores, dtype="float64")
    positives = int(numpy.sum(truth))
    negatives = int(numpy.sum(~truth))
    if positives == 0 or negatives == 0:
        return 0.0
    ranks = _average_ranks(values)
    positive_rank_sum = float(numpy.sum(ranks[truth]))
    return (positive_rank_sum - positives * (positives + 1) / 2.0) / (
        positives * negatives
    )


def best_threshold(
    labels: numpy.ndarray,
    scores: numpy.ndarray,
    max_fpr: float = 0.05,
    default: float = 0.70,
) -> tuple[float, dict[str, float]]:
    truth = numpy.asarray(labels, dtype=bool)
    values = numpy.asarray(scores, dtype="float64")
    best_value: float | None = None
    best_metrics: dict[str, float] | None = None
    for threshold in numpy.linspace(0.01, 0.99, 99):
        metrics = binary_metrics(truth, values >= threshold)
        if metrics["false_positive_rate"] <= max_fpr and (
            best_metrics is None or metrics["f1"] > best_metrics["f1"]
        ):
            best_value = float(threshold)
            best_metrics = metrics
    if best_value is not None and best_metrics is not None:
        return best_value, best_metrics
    fallback_value = default
    fallback_metrics = binary_metrics(truth, values >= fallback_value)
    for threshold in numpy.linspace(0.01, 0.99, 99):
        metrics = binary_metrics(truth, values >= threshold)
        if (
            metrics["false_positive_rate"],
            -metrics["f1"],
        ) < (
            fallback_metrics["false_positive_rate"],
            -fallback_metrics["f1"],
        ):
            fallback_value = float(threshold)
            fallback_metrics = metrics
    return fallback_value, fallback_metrics


def _average_ranks(values: numpy.ndarray) -> numpy.ndarray:
    order = numpy.argsort(values, kind="mergesort")
    sorted_values = values[order]
    ranks = numpy.empty(len(values), dtype="float64")
    index = 0
    while index < len(values):
        end = index
        while end + 1 < len(values) and sorted_values[end + 1] == sorted_values[index]:
            end += 1
        average = (index + end) / 2.0 + 1.0
        ranks[order[index : end + 1]] = average
        index = end + 1
    return ranks


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)
