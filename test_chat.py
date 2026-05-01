import urllib.request, json, sys

# Force UTF-8 output on Windows to handle emoji in replies
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')



def post(path, body):
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def get(path):
    with urllib.request.urlopen(BASE + path) as resp:
        return json.loads(resp.read())

def delete(path):
    req = urllib.request.Request(BASE + path, method='DELETE')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())

def sep(title):
    print("\n" + "=" * 60)
    print("TEST:", title)
    print("=" * 60)

errors = []

try:
    sep("1: Health check")
    r = get('/')
    print(json.dumps(r, indent=2))

    sep("2: Greeting")
    r = post('/api/v1/chat', {'userId': 'testuser1', 'message': 'Hello!'})
    print("Reply:", r['reply'][:200])
    print("Suggestions:", len(r['suggestions']))
    print("Intent:", r['metadata']['intent'])
    assert r['metadata']['intent'] == 'greeting', "Expected greeting intent"

    sep("3: Travel planning with destination + budget + duration")
    r = post('/api/v1/chat', {'userId': 'testuser1', 'message': 'I want to visit Paris with a budget of 1500 dollars for 7 days'})
    print("Reply:", r['reply'][:400])
    print("Suggestions count:", len(r['suggestions']))
    for s in r['suggestions'][:3]:
        cost = s.get('estimated_cost_usd')
        cost_str = str(cost) if cost else 'free'
        print("  -", s['name'], "(" + s['activity_type'] + ")", "~$" + cost_str)
    ctx = r['metadata']['context_summary']
    print("Context:", ctx)
    assert ctx['destination'] == 'Paris', "Expected Paris as destination, got: " + str(ctx['destination'])
    assert ctx['budget_usd'] == 1500.0, "Expected 1500 budget"
    assert ctx['duration_days'] == 7, "Expected 7 day duration"

    sep("4: Follow-up message (context retention)")
    r = post('/api/v1/chat', {'userId': 'testuser1', 'message': 'What adventure activities can I do there?'})
    print("Reply:", r['reply'][:300])
    ctx = r['metadata']['context_summary']
    print("Destination still:", ctx['destination'])
    assert ctx['destination'] == 'Paris', "Context not retained!"

    sep("5: Budget adjustment")
    r = post('/api/v1/chat', {'userId': 'testuser1', 'message': 'Actually I only have 400 dollars'})
    print("Reply:", r['reply'][:300])
    new_budget = r['metadata']['context_summary']['budget_usd']
    print("New budget:", new_budget)
    assert new_budget == 400.0, "Budget not updated, got: " + str(new_budget)

    sep("6: History endpoint")
    r = get('/api/v1/chat/testuser1/history')
    print("Total messages:", r['total_messages'])
    print("Context:", r['context'])
    assert r['total_messages'] >= 8, "Expected at least 8 messages (user + assistant turns)"

    sep("7: Clear history")
    r = delete('/api/v1/chat/testuser1/history')
    print(r['message'])

    sep("8: History cleared - expect 404")
    try:
        r = get('/api/v1/chat/testuser1/history')
        errors.append("Expected 404 after clear but got response")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print("Got expected 404 - history was cleared OK")
        else:
            errors.append("Expected 404 but got: " + str(e.code))

    sep("9: Empty message guard")
    try:
        r = post('/api/v1/chat', {'userId': 'testuser1', 'message': '   '})
        errors.append("Expected 422 for blank message but got response")
    except urllib.error.HTTPError as e:
        if e.code in (400, 422):
            print("Got expected", e.code, "for blank message OK")
        else:
            errors.append("Expected 400/422 but got: " + str(e.code))

except Exception as e:
    errors.append(str(e))
    import traceback; traceback.print_exc()

print("\n" + "=" * 60)
if errors:
    print("FAILURES:", errors)
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
