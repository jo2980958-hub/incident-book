from app.webhooks import parse_webhook, sign, verify_signature


def test_sign_and_verify_round_trip():
    secret = "demo-shared-secret"
    body = b'{"event_type": "motion_detected", "device_id": "dev_counter_cam_01"}'
    signature = sign(secret, body)
    assert verify_signature(secret, body, signature) is True


def test_verify_rejects_tampered_body():
    secret = "demo-shared-secret"
    body = b'{"event_type": "motion_detected"}'
    signature = sign(secret, body)
    tampered = b'{"event_type": "button_press"}'
    assert verify_signature(secret, tampered, signature) is False


def test_verify_rejects_wrong_secret():
    body = b'{"event_type": "motion_detected"}'
    signature = sign("secret-a", body)
    assert verify_signature("secret-b", body, signature) is False


def test_verify_rejects_missing_signature():
    body = b'{"event_type": "motion_detected"}'
    assert verify_signature("demo-shared-secret", body, "") is False


def test_parse_webhook_returns_dict():
    body = b'{"event_type": "motion_detected", "device_id": "d1"}'
    parsed = parse_webhook(body)
    assert parsed["event_type"] == "motion_detected"
    assert parsed["device_id"] == "d1"
