from plant import Plant, Flower, Vegetable


def main():

    # Information:
    # Default plant height = 20 cm
    # Default flower height = 30 cm, color = "Green"
    # Default vegetable height = 10 cm, harvest days = 90
    #
    # Plant care instructions = "Water regularly and provide adequate sunlight."
    # Flower care instructions = "Water regularly, provide full sun, and deadhead spent blooms."
    # Vegetable care instructions = "Water regularly, provide full sun, and fertilize every two weeks."

    plants = [
        Plant("Fern", 35),
        Flower("Rose", 45, "red"),
        Flower("Marigold", 25, "orange"),
        Vegetable("Tomato", 80, 70),
        Vegetable("Lettuce", 20, 45),
        Plant("Spanish Moss"),
        Flower("Petunias"),
        Vegetable("Carrots")
    ]

    print("Garden Inventory")
    print("----------------")

    for plant in plants:
        print(plant)
        print("Care:", plant.care_instructions())
        print()


main()
