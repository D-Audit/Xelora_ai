import requests

API_URL = "https://rne.sdms.gov.rw/api/v1/public/results/by-index?indexNumber="
INDEX_PREFIX = "240950OLC"
INDEX_SUFFIX = "2026"


def fetch_marks(index):
    try:
        url = API_URL + index
        res = requests.get(url)

        if (res.status_code == 404):
            return None

        data = res.json()
        return data
    except KeyboardInterrupt:
        raise SystemExit(0)

for n in range(1, 121):
    index = ""
    if n < 10:
        index = INDEX_PREFIX + f"00{n}" + INDEX_SUFFIX
    elif n < 100:
        index = INDEX_PREFIX + f"0{n}" + INDEX_SUFFIX
    else:
        index = INDEX_PREFIX + f"{n}" + INDEX_SUFFIX

    data = fetch_marks(index)
    print("-------------")
    if not data == None:
        print(f"Name: {data['studentNames']}")
        print(f"Index number: {data['studentIndexNumber']}")
        print(f"Verdict: {data['division']}")
        print(f"Placed at: {data['placedSchoolName']}")
        print(f"Combination: {data['placedCombinationName']}")
        print(f"Percentage: {data['weightedPercent']}")
    else:
        print(f"Results for {index} not found!")
    print("-------------")