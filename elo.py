def expected_score(r_a, r_b):
    return 1 / (1 + 10 ** ((r_b - r_a) / 400))

def new_rating(r_old, score_actual, score_expected, k):
    return round(r_old + k * (score_actual - score_expected))
