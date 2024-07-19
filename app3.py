import streamlit as st
import pandas as pd
from ortools.linear_solver import pywraplp

st.title("Cattle Feed Optimization")

# intro

st.write('Hello! Here you can optimize feed for your cattle!')

# Read specific columns from each Excel sheet

concentrates_df = pd.read_excel('feed.xlsx', sheet_name='Concentrates').dropna(subset = 'FeedStuff')
dry_fodder_df = pd.read_excel('feed.xlsx', sheet_name='Dry Fodder').dropna(subset = 'FeedStuff')
green_fodder_df = pd.read_excel('feed.xlsx', sheet_name='Green Fodder').dropna(subset = 'FeedStuff')
requirements_df = pd.read_excel('feed.xlsx', sheet_name='Requirements')

# Fill NaN values with empty strings
requirements_df.fillna("", inplace=True)
concentrates_df.fillna(0, inplace=True)
dry_fodder_df.fillna(0, inplace=True)
green_fodder_df.fillna(0, inplace=True)

# Let users select the animal type
animal_type = st.selectbox('Select Animal Type', requirements_df['Type'].unique())

# Display requirements for users to choose from
st.dataframe(requirements_df)

# Filter requirements based on selected animal type
selected_requirements = requirements_df[requirements_df['Type'] == animal_type]

# Select ingredients from each category
selected_concentrates = st.multiselect('Select Concentrates', concentrates_df['FeedStuff'].unique())
selected_dry_fodder = st.multiselect('Select Dry Fodder', dry_fodder_df['FeedStuff'].unique())
selected_green_fodder = st.multiselect('Select Green Fodder', green_fodder_df['FeedStuff'].unique())

# Check if at least one option is selected from each category
if len(selected_concentrates) == 0 or len(selected_dry_fodder) == 0 or len(selected_green_fodder) == 0:
    st.warning('Please select at least one option from each category.')

# Collect prices for selected ingredients
prices = {}
def collect_prices(selected_ingredients, category_name):
    for ingredient in selected_ingredients:
        price = st.number_input(f'Enter price for {ingredient} ({category_name})', min_value=0.0, value=0.0, step=0.01)
        prices[ingredient] = price

collect_prices(selected_concentrates, 'Concentrates')
collect_prices(selected_dry_fodder, 'Dry Fodder')
collect_prices(selected_green_fodder, 'Green Fodder')

# Combine selected ingredients into a single DataFrame
selected_ingredients = selected_concentrates + selected_dry_fodder + selected_green_fodder
filtered_ingredients = pd.concat([
    concentrates_df[concentrates_df['FeedStuff'].isin(selected_concentrates)],
    dry_fodder_df[dry_fodder_df['FeedStuff'].isin(selected_dry_fodder)],
    green_fodder_df[green_fodder_df['FeedStuff'].isin(selected_green_fodder)]
])

# Display the filtered ingredients with prices

st.write('You can check the ingredients along with nutritional values in the table below:')
filtered_ingredients['Price'] = filtered_ingredients['FeedStuff'].map(prices)
st.write(filtered_ingredients[['FeedStuff', 'TDN', 'ME', 'Ca', 'P', 'CP', 'Price']])

# Optimization process
if st.button('Optimize') and len(selected_ingredients) >= 3:
    # Extract data for optimization
    ingredient_names = filtered_ingredients['FeedStuff'].tolist()
    costs = filtered_ingredients['Price'].tolist()

    # Create the solver
    solver = pywraplp.Solver.CreateSolver('GLOP')
    if not solver:
        st.error("Solver not created.")
    else:
        # Define decision variables
        ingredient_vars = [solver.NumVar(0, solver.infinity(), ingredient) for ingredient in ingredient_names]

        # Define slack variables for all nutrients
        slack_vars = {}
        penalty_factor = 5
        nutrient_columns = ['TDN', 'ME', 'Ca', 'P', 'CP']
        for nutrient in nutrient_columns:
            slack_vars[nutrient] = solver.NumVar(0, solver.infinity(), f'slack_{nutrient}')

        # Define the objective function
        objective = solver.Objective()
        for i, cost in enumerate(costs):
            objective.SetCoefficient(ingredient_vars[i], cost)
            for nutrient in nutrient_columns:
                objective.SetCoefficient(slack_vars[nutrient], penalty_factor)
        objective.SetMinimization()

        # Define the nutritional constraints for each nutrient
        for nutrient in nutrient_columns:        
            total = 0
            for i, ingredient in enumerate(ingredient_names):
                requirement = float(selected_requirements[nutrient].values[0])
                nutrient_content = filtered_ingredients[filtered_ingredients['FeedStuff'] == ingredient][nutrient].values[0]
                pdt = ingredient_vars[i]*nutrient_content
                total = total+pdt
            solver.Add(total + slack_vars[nutrient] >= requirement * 100)

        # Ensure at least one ingredient from each category is included
        category_constraints = [
            selected_concentrates,
            selected_dry_fodder,
            selected_green_fodder
        ]
        for category in category_constraints:
            total = solver.Sum([ingredient_vars[i] for i, ingredient in enumerate(ingredient_names) if ingredient in category])
            solver.Add(total >= 1)

        # Add constraint to sum of quantities equal to 100
        quantity = 0
        for ing in ingredient_vars:
            quantity += ing
        solver.Add(quantity == 100)

        # Solve the optimization problem
        status = solver.Solve()

        # Display the results
        if status == pywraplp.Solver.OPTIMAL:
            st.header('Optimal Solution Found:')
            total_nutrient_values = {nutrient: 0 for nutrient in nutrient_columns}
            total_cost = 0
            
            for i, ingredient in enumerate(ingredient_names):
                amount = ingredient_vars[i].solution_value()
                cost = ingredient_vars[i].solution_value() * costs[i]
                st.write(f'{ingredient}: {amount:.2f} kg')
                total_cost += cost
                
                # Calculate total nutritional values
                for nutrient in nutrient_columns:
                    nutrient_content = filtered_ingredients[filtered_ingredients['FeedStuff'] == ingredient][nutrient].values[0]
                    total_nutrient_values[nutrient] += amount * nutrient_content

            st.header(f'Total Cost: Rs {total_cost:.2f}')

            # Display total nutritional values
            st.header(f'Total Nutritional Values:')
            for nutrient in nutrient_columns:
                value = total_nutrient_values[nutrient]/100
                requirement = float(selected_requirements[nutrient].values[0])
                if value < requirement:
                    st.markdown(f"**{nutrient}: {value:.2f}** (Less than required: {requirement:.2f})", unsafe_allow_html=True)
                else:
                    st.write(f'{nutrient}: {value:.2f}')

        else:
            st.write('No optimal solution found.')
