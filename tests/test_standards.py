"""
Tests for Standards, Saved Standards, and Compliance Checker.
"""
def register_and_get_token(client, email, name):
    res = client.post("/api/auth/register", json={
        "name": name,
        "email": email,
        "password": "password123",
    })
    return res.json()["access_token"]


def test_standards_search_and_saved_isolation(client):
    # Standards search
    res = client.get("/api/standards?q=kettle")
    assert res.status_code == 200
    data = res.json()
    assert "results" in data
    assert len(data["results"]) >= 1

    # Standard detail
    std_id = data["results"][0]["id"]
    detail = client.get(f"/api/standards/{std_id}")
    assert detail.status_code == 200
    assert "IS 302-2-15" in detail.json()["number"]

    # User A saves a standard
    token_a = register_and_get_token(client, "saver_a@test.com", "Saver A")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    token_b = register_and_get_token(client, "saver_b@test.com", "Saver B")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    save_res = client.post("/api/saved", json={
        "standard_id": "std-001",
        "standard_reference": "IS 302-2-15",
        "title": "Safety of Household Appliances",
        "category": "Electrical Appliances",
    }, headers=headers_a)
    assert save_res.status_code == 201
    saved_id = save_res.json()["id"]

    # User A sees it in saved list
    saved_a = client.get("/api/saved", headers=headers_a)
    assert len(saved_a.json()) >= 1
    assert saved_a.json()[0]["standard_reference"] == "IS 302-2-15"

    # User B sees empty saved list (User isolation)
    saved_b = client.get("/api/saved", headers=headers_b)
    assert len(saved_b.json()) == 0

    # User A deletes saved standard
    del_res = client.delete(f"/api/saved/{saved_id}", headers=headers_a)
    assert del_res.status_code == 204


def test_compliance_check(client):
    token = register_and_get_token(client, "compliance_user@test.com", "Compliance Tester")
    headers = {"Authorization": f"Bearer {token}"}

    check_res = client.post("/api/compliance", json={
        "product_name": "Commercial Induction Cooktop",
        "product_category": "Electrical Appliances",
        "description": "2000W induction cooktop with digital display and automatic shutoff",
    }, headers=headers)

    assert check_res.status_code == 201
    result = check_res.json()
    assert result["product"] == "Commercial Induction Cooktop"
    assert "overall_score" in result
    assert "breakdown" in result
    assert len(result["breakdown"]) > 0

    # Retrieve past compliance reports
    reports_res = client.get("/api/compliance", headers=headers)
    assert reports_res.status_code == 200
    assert len(reports_res.json()) >= 1
