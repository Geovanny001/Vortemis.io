import numpy

from vortemis.application.evaluation import best_threshold, binary_metrics, roc_auc


def test_binary_metrics_perfect_classifier() -> None:
    metrics = binary_metrics(
        numpy.array([1, 1, 0, 0]),
        numpy.array([1, 1, 0, 0]),
    )

    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
    assert metrics["f1"] == 1.0
    assert metrics["false_positive_rate"] == 0.0


def test_binary_metrics_mixed_classifier() -> None:
    metrics = binary_metrics(
        numpy.array([1, 1, 0, 0]),
        numpy.array([1, 0, 1, 0]),
    )

    assert metrics["true_positive"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5
    assert metrics["f1"] == 0.5
    assert metrics["false_positive_rate"] == 0.5


def test_roc_auc_perfect_and_inverse() -> None:
    labels = numpy.array([1, 1, 0, 0])

    assert roc_auc(labels, numpy.array([0.9, 0.8, 0.2, 0.1])) == 1.0
    assert roc_auc(labels, numpy.array([0.1, 0.2, 0.8, 0.9])) == 0.0


def test_roc_auc_with_ties() -> None:
    labels = numpy.array([1, 0])
    scores = numpy.array([0.5, 0.5])

    assert roc_auc(labels, scores) == 0.5


def test_best_threshold_respects_fpr_limit() -> None:
    threshold, metrics = best_threshold(
        labels=numpy.array([1, 1, 0, 0]),
        scores=numpy.array([0.9, 0.4, 0.8, 0.1]),
        max_fpr=0.0,
    )

    assert 0.8 < threshold <= 0.9
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["recall"] == 0.5


def test_best_threshold_prefers_fpr_limit_over_default_f1() -> None:
    threshold, metrics = best_threshold(
        labels=numpy.array([1, 1, 1, 0, 0, 0]),
        scores=numpy.array([0.9, 0.6, 0.5, 0.7, 0.45, 0.1]),
        max_fpr=0.0,
        default=0.5,
    )

    assert threshold > 0.7
    assert metrics["false_positive_rate"] == 0.0
    assert metrics["f1"] == 0.5
