from ai_engine import build_messages


def test_build_messages_adds_clarity_instruction_for_chat_mode() -> None:
    messages = build_messages(
        [{"role": "user", "content": "What is network security?"}],
        "chat",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any("The user wants very easy-to-understand answers." in content for content in system_messages)
    assert any("1. Answer" in content for content in system_messages)
    assert any("2. Step by step" in content for content in system_messages)
    assert any("3. Example" in content for content in system_messages)
    assert any("exactly one simple real-world example" in content for content in system_messages)


def test_build_messages_skips_clarity_instruction_for_image_mode() -> None:
    messages = build_messages(
        [{"role": "user", "content": "Create an image of a secure network"}],
        "image",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert not any(
        "The user prefers very easy-to-understand answers." in content
        for content in system_messages
    )
