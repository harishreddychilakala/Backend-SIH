"""
Tests for Chat, Conversations, and User Data Isolation.
"""
def register_and_get_token(client, email, name):
    res = client.post("/api/auth/register", json={
        "name": name,
        "email": email,
        "password": "password123",
    })
    return res.json()["access_token"]


def test_chat_creation_and_user_isolation(client):
    # Create User A
    token_a = register_and_get_token(client, "user_a@test.com", "User A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Create User B
    token_b = register_and_get_token(client, "user_b@test.com", "User B")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # User A starts a chat
    chat_res = client.post("/api/chat", json={
        "content": "Which standard applies to electric kettles?",
        "title": "Electric Kettle Standard Query",
    }, headers=headers_a)

    assert chat_res.status_code == 201
    chat_data = chat_res.json()
    conv_id = chat_data["id"]
    assert len(chat_data["messages"]) == 2  # user msg + ai msg
    assert chat_data["messages"][0]["role"] == "user"
    assert chat_data["messages"][1]["role"] == "assistant"

    # User A can retrieve their conversation list
    list_a = client.get("/api/conversations", headers=headers_a)
    assert list_a.status_code == 200
    assert len(list_a.json()) >= 1
    assert any(c["id"] == conv_id for c in list_a.json())

    # CRITICAL: User B CANNOT see User A's conversation list
    list_b = client.get("/api/conversations", headers=headers_b)
    assert list_b.status_code == 200
    assert not any(c["id"] == conv_id for c in list_b.json())

    # CRITICAL: User B CANNOT get User A's conversation details (404)
    get_b = client.get(f"/api/conversations/{conv_id}", headers=headers_b)
    assert get_b.status_code == 404

    # CRITICAL: User B CANNOT send message into User A's conversation (404)
    msg_b = client.post(f"/api/chat/{conv_id}/messages", json={
        "content": "Trying to post to another user conversation"
    }, headers=headers_b)
    assert msg_b.status_code == 404

    # User A CAN send a message in their own conversation
    msg_a = client.post(f"/api/chat/{conv_id}/messages", json={
        "content": "What are the testing requirements for it?"
    }, headers=headers_a)
    assert msg_a.status_code == 200
    assert msg_a.json()["role"] == "assistant"

    # User A can delete their conversation
    del_res = client.delete(f"/api/conversations/{conv_id}", headers=headers_a)
    assert del_res.status_code == 204
