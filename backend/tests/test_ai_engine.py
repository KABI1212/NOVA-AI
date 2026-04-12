from ai_engine import build_messages


def test_build_messages_adds_clarity_and_presentation_instructions_for_chat_mode() -> None:
    messages = build_messages(
        [{"role": "user", "content": "What is network security?"}],
        "chat",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "The user wants clear, easy-to-understand answers." in content
        for content in system_messages
    )
    assert any(
        "Make heading and subheading text bold" in content
        for content in system_messages
    )
    assert any(
        "break the reply into short Markdown sections" in content
        for content in system_messages
    )
    assert any(
        "add relevant emojis" in content
        for content in system_messages
    )
    assert any(
        "orchestration intelligence" in content
        for content in system_messages
    )
    assert any(
        "supportive expert partner" in content
        for content in system_messages
    )


def test_build_messages_skips_clarity_instruction_for_image_mode() -> None:
    messages = build_messages(
        [{"role": "user", "content": "Create an image of a secure network"}],
        "image",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert not any(
        "The user wants clear, easy-to-understand answers." in content
        for content in system_messages
    )
    assert any(
        "Make heading and subheading text bold" in content
        for content in system_messages
    )


def test_build_messages_adds_multi_question_exam_instruction() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": (
                    "Answer all questions from this question paper. "
                    "There are 4 questions of 2 marks and 3 questions of 8 marks."
                ),
            }
        ],
        "documents",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "Answer all visible questions and sub-questions" in content
        for content in system_messages
    )
    assert any(
        "Match each answer's depth to its own mark value" in content
        for content in system_messages
    )
    assert any(
        "Do not stop after only a few answers" in content
        for content in system_messages
    )


def test_build_messages_adds_diagram_and_long_answer_guidance() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": "Draw a neat diagram of SSH architecture for a 16 mark assignment answer.",
            }
        ],
        "documents",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "The user wants a clear diagram-style answer." in content
        for content in system_messages
    )
    assert any(
        "Do not draw rough ASCII art" in content
        for content in system_messages
    )
    assert any(
        "Match the depth to this 16-mark question." in content
        for content in system_messages
    )
    assert any(
        "Target about 3000 words." in content
        for content in system_messages
    )


def test_build_messages_targets_requested_depth_for_8_mark_answers() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": "Explain SSL handshake for 8 marks.",
            }
        ],
        "documents",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "Match the depth to this 8-mark question." in content
        for content in system_messages
    )
    assert any(
        "Target about 1500 words." in content
        for content in system_messages
    )


def test_build_messages_targets_requested_depth_for_10_mark_answers() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": "Explain transport layer security for 10 marks.",
            }
        ],
        "documents",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "Match the depth to this 10-mark question." in content
        for content in system_messages
    )
    assert any(
        "Target about 2000 words." in content
        for content in system_messages
    )


def test_build_messages_keeps_2_mark_answers_brief_and_simple() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": "What is a firewall for 2 marks?",
            }
        ],
        "documents",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "1 to 2 short lines" in content
        for content in system_messages
    )
    assert any(
        "one small supporting detail" in content
        for content in system_messages
    )


def test_build_messages_strengthens_comparison_table_guidance() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": "Compare TCP and UDP.",
            }
        ],
        "documents",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "Use a clear Markdown table as the main structure." in content
        for content in system_messages
    )
    assert any(
        "Make the first column the comparison aspect or parameter." in content
        for content in system_messages
    )


def test_build_messages_enables_nova_special_mode_for_full_power_requests() -> None:
    messages = build_messages(
        [
            {
                "role": "user",
                "content": "Use full power and explain recursion for advanced learners.",
            }
        ],
        "chat",
    )

    system_messages = [
        message["content"] for message in messages if message.get("role") == "system"
    ]

    assert any(
        "The user explicitly requested NOVA Special Mode." in content
        for content in system_messages
    )
    assert any(
        "Optimize for quality over speed." in content
        for content in system_messages
    )
