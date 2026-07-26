import json
from unittest.mock import MagicMock

import pytest

from trade_pipeline.consumer.dlq import DlqProducer, DlqPublishError


def _fake_message(topic="trades", partition=0, offset=42, value=b'{"trade_id": "t-1"}'):
    message = MagicMock()
    message.topic.return_value = topic
    message.partition.return_value = partition
    message.offset.return_value = offset
    message.value.return_value = value
    return message


def _dlq_producer_with_delivery(*, fails: bool) -> tuple[DlqProducer, MagicMock]:
    kafka_producer = MagicMock()

    def produce(topic, value, callback):
        err = "boom" if fails else None
        callback(err, None)

    kafka_producer.produce.side_effect = produce
    return DlqProducer(producer=kafka_producer), kafka_producer


def test_dlq_topic_naming():
    dlq, _ = _dlq_producer_with_delivery(fails=False)
    assert dlq.dlq_topic_for("trades") == "trades-dlq"


def test_send_publishes_envelope_with_expected_fields():
    dlq, kafka_producer = _dlq_producer_with_delivery(fails=False)
    message = _fake_message(topic="trades", partition=2, offset=99)

    dlq.send(message, ValueError("bad payload"))

    kafka_producer.produce.assert_called_once()
    call = kafka_producer.produce.call_args
    assert call.args[0] == "trades-dlq"
    envelope = json.loads(call.kwargs["value"])
    assert envelope["error_type"] == "ValueError"
    assert envelope["error_message"] == "bad payload"
    assert envelope["original_topic"] == "trades"
    assert envelope["original_partition"] == 2
    assert envelope["original_offset"] == 99
    assert envelope["payload"] == '{"trade_id": "t-1"}'
    assert "failed_at" in envelope


def test_send_flushes_before_returning():
    dlq, kafka_producer = _dlq_producer_with_delivery(fails=False)
    dlq.send(_fake_message(), ValueError("x"))
    kafka_producer.flush.assert_called_once()


def test_send_raises_when_delivery_fails():
    dlq, _ = _dlq_producer_with_delivery(fails=True)
    with pytest.raises(DlqPublishError):
        dlq.send(_fake_message(), ValueError("x"))
