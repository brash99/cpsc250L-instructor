def probability(odds_line):
    o1 = odds_line[0]
    o2 = odds_line[1]
    o3 = odds_line[2]

    p1 = abs(min(100,o1))/(100+abs(o1))
    p2 = abs(min(100,o2))/(100+abs(o2))
    p3 = abs(min(100,o3))/(100+abs(o3))

    p_sum = p1 + p2 + p3
    vig = p_sum - 1
    p1 = p1/p_sum
    p2 = p2/p_sum
    p3 = p3/p_sum

    return p1, p2, p3, vig

if __name__ == "__main__":

    line = input("Input the odds, on one line, separated by commas: \n")
    odds = line.split(",")
    odds = [int(odds[0]),int(odds[1]),int(odds[2])]
    prob1, prob2, prob3, vig = probability(odds)
    print(f"Probabilities are: {prob1:.3f}, {prob2:.3f}, {prob3:.3f}")
    print(f"Vig is: {vig:.3f}")
