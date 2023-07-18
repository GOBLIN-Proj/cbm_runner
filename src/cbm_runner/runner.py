import cbm_runner.generated_input_data as input_data_path
from cbm_runner.cbm_data_factory import DataFactory
from cbm_runner.cbm_runner_data_manager import DataManager

from libcbm.model.cbm import cbm_simulator
from libcbm.input.sit import sit_cbm_factory

import pandas as pd

class Runner:
    def __init__(self, config_path, calibration_year, forest_end_year, afforest_data, scenario_data):
        self.path = input_data_path.get_local_dir()
        self.cbm_data_class = DataFactory(config_path,calibration_year,forest_end_year, afforest_data, scenario_data)
        self.data_manager_class = DataManager(config_path)

        self.INDEX = [int(i) for i in afforest_data.scenario.unique()]
        self.forest_end_year = forest_end_year


    def generate_input_data(self):

        path = self.path

        self.cbm_data_class.clean_data_dir(path)
        self.cbm_data_class.make_data_dirs(self.INDEX, path)

        for i in self.INDEX:
            self.cbm_data_class.make_classifiers(i, path)
            self.cbm_data_class.make_config_json(i, path)
            self.cbm_data_class.make_age_classes(i, path)
            self.cbm_data_class.make_yield_curves(i, path)
            self.cbm_data_class.make_inventory(i, path)
            self.cbm_data_class.make_disturbance_events(i, path)
            self.cbm_data_class.make_disturbance_type(i, path)
            self.cbm_data_class.make_transition_rules(i, path)


    def run_aggregate_scenarios(self):

        forest_data = pd.DataFrame()
        aggregate_forest_data = pd.DataFrame()
        
        for i in self.INDEX:
            forest_data = self.cbm_aggregate_scenario(i)

            forest_data_copy = forest_data.copy(deep=True)


            aggregate_forest_data = pd.concat(
            [aggregate_forest_data, forest_data_copy], ignore_index=True
            )

        return aggregate_forest_data
    
    
    def run_flux_scenarios(self):

        forest_data = pd.DataFrame()
        fluxes_data = pd.DataFrame()
        fluxes_forest_data = pd.DataFrame()
        
        for i in self.INDEX:
            forest_data = self.cbm_aggregate_scenario(i)

            fluxes_data = self.cbm_scenario_fluxes(forest_data)

            fluxes_forest_data = pd.concat(
            [fluxes_forest_data, fluxes_data], ignore_index=True
            )

        return fluxes_forest_data


    def cbm_aggregate_scenario(self, sc):

        forest_baseline_year = self.data_manager_class.forest_baseline_year
        forestry_end_year = self.forest_end_year
        path = self.path

        years = forestry_end_year - forest_baseline_year

        year_range = [
            year + 1 for year in range(forest_baseline_year - 1, forestry_end_year)
        ]

        sit, classifiers, inventory = self.cbm_data_class.set_input_data_dir(sc, path)

        classifier_config = sit_cbm_factory.get_classifiers(
            sit.sit_data.classifiers, sit.sit_data.classifier_values
        )

        results, reporting_func = cbm_simulator.create_in_memory_reporting_func(
            classifier_map={
                x["id"]: x["value"] for x in classifier_config["classifier_values"]
            }
        )

        # Simulation
        with sit_cbm_factory.initialize_cbm(sit) as cbm:
            # Create a function to apply rule based disturbance events and transition rules based on the SIT input
            rule_based_processor = sit_cbm_factory.create_sit_rule_based_processor(
                sit, cbm
            )
            # The following line of code spins up the CBM inventory and runs it through 200 timesteps.
            cbm_simulator.simulate(
                cbm,
                n_steps=years,
                classifiers=classifiers,
                inventory=inventory,
                pre_dynamics_func=rule_based_processor.pre_dynamics_func,
                reporting_func=reporting_func,
            )

        pi = results.pools.merge(results.classifiers)

        biomass_pools = [
            "SoftwoodMerch",
            "SoftwoodFoliage",
            "SoftwoodOther",
            "SoftwoodCoarseRoots",
            "SoftwoodFineRoots",
            "HardwoodMerch",
            "HardwoodFoliage",
            "HardwoodOther",
            "HardwoodCoarseRoots",
            "HardwoodFineRoots",
        ]

        dom_pools = [
            "AboveGroundVeryFastSoil",
            "BelowGroundVeryFastSoil",
            "AboveGroundFastSoil",
            "BelowGroundFastSoil",
            "MediumSoil",
            "AboveGroundSlowSoil",
            "BelowGroundSlowSoil",
            "SoftwoodStemSnag",
            "SoftwoodBranchSnag",
            "HardwoodStemSnag",
            "HardwoodBranchSnag",
        ]

        annual_carbon_stocks = pd.DataFrame(
            {
                "Year": pi["timestep"],
                "Biomass": pi[biomass_pools].sum(axis=1) * -1,
                "DOM": pi[dom_pools].sum(axis=1) * -1,
                "Total Ecosystem": pi[biomass_pools + dom_pools].sum(axis=1) * -1,
                "HWP":pi["Products"]
            }
        )

        annual_carbon_stocks = annual_carbon_stocks.groupby(["Year"], as_index=False)[
            ["Biomass", "DOM", "Total Ecosystem", "HWP"]
        ].sum()

        annual_carbon_stocks["Year"] = year_range
        annual_carbon_stocks["Scenario"] = sc

        return annual_carbon_stocks
    
    
    def cbm_scenario_fluxes(self, forest_data):

        fluxes = pd.DataFrame(columns=forest_data.columns)

        for i in forest_data.index:
            if i > 0:
                fluxes.loc[i - 1, "Year"] = int(forest_data.loc[i, "Year"])
                fluxes.loc[i - 1, "Scenario"] = int(forest_data.loc[i, "Scenario"])
                fluxes.loc[i - 1, "Biomass"] = (
                    forest_data.loc[i, "Biomass"] - forest_data.loc[i - 1, "Biomass"]
                )
                fluxes.loc[i - 1, "DOM"] = (
                    forest_data.loc[i, "DOM"] - forest_data.loc[i - 1, "DOM"]
                )
                fluxes.loc[i - 1, "Total Ecosystem"] = (
                    forest_data.loc[i, "Total Ecosystem"]
                    - forest_data.loc[i - 1, "Total Ecosystem"]
                )

                fluxes.loc[i - 1, "HWP"] = (
                    forest_data.loc[i, "HWP"]
                    - forest_data.loc[i - 1, "HWP"]
                )

        return fluxes