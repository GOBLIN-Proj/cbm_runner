from cbm_runner.loader import Loader
from cbm_runner.cbm_runner_data_manager import DataManager
import pandas as pd

class ForestStand:
    """Represents a single forest stand."""
    
    def __init__(self, species, yield_class, soil, area, age=0):
        self.species = species
        self.yield_class = yield_class
        self.soil = soil
        self.area = area
        self.age = age
        self.since_last_dist = None


    def age_stand(self):
        """Increases the age of the stand by one year."""
        self.age += 1

    def disturb(self):
        """Increases time since last disturbance by one year."""
        if self.since_last_dist is None:
            self.since_last_dist = 0
        else:
            self.since_last_dist += 1

    def reset_dist(self):
        """Resets time since last disturbance to zero."""
     
        self.since_last_dist = 0

class DisturbedForestStand:
    """Represents a single forest stand."""
    
    def __init__(self, year, species, yield_class, soil):
        self.species = species
        self.yield_class = yield_class
        self.soil = soil
        self.dist = None
        self.area = None
        self.year = year


class AfforestationTracker:
    """Tracks afforestation efforts over time."""
    
    def __init__(self):
        self.loader_class = Loader()
        self.data_manager_class = DataManager()
        self.disturbance_timing = self.loader_class.disturbance_time()
        self.stands = []
        self.disturbed_stands = []

    
    def afforest(self, area, species, yield_class, soil, age=0):
        """Add an afforestation event to the tracker."""
        stand = ForestStand(species, yield_class, soil, area, age)
        self.stands.append(stand)


    def move_to_next_age(self):
        """Age all stands by one year."""
        for stand in self.stands:
            stand.age_stand()


    def forest_disturbance(self, year, species, yield_class, soil, proportion):
        """Add a disturbance event to the tracker."""
        disturbance_types = self.disturbance_timing["disturbance_id"].unique()
        yield_name = self.data_manager_class.get_yield_name_dict()

        for stand in self.stands:
            for dist in disturbance_types:
                disturbed_area = 0

                if stand.yield_class == yield_class and stand.species == species and stand.soil == soil:

                    try:
                        yc = yield_name[species][yield_class]
                    except KeyError:
                        yc = None

                    if yc is not None:
                        mask = ((self.disturbance_timing.index == yc) & (self.disturbance_timing["disturbance_id"] == dist))
                        if not self.disturbance_timing.loc[mask].empty:
                            if stand.age >= self.disturbance_timing.loc[mask, "sw_age_min"].item() and stand.age <= self.disturbance_timing.loc[mask,"sw_age_max"].item():
                                dist_stand = DisturbedForestStand(year,species, yield_class, soil)
                                
                                if dist == "DISTID1":
                                    disturbed_area = stand.area * proportion[dist]
                                    replant = ForestStand(species, yield_class, soil, disturbed_area)
                                    self.stands.append(replant)
                                    stand.area = stand.area * (1 - proportion[dist])

                                    dist_stand.dist = dist
                                    dist_stand.area = disturbed_area
                                    dist_stand.species = species
                                    dist_stand.yield_class = yield_class
                                    dist_stand.soil = soil
                                    self.disturbed_stands.append(dist_stand)

                                elif stand.since_last_dist is None or stand.since_last_dist >= self.disturbance_timing.loc[mask, "min years since dist"].item():
                                    disturbed_area = stand.area * proportion[dist]
                                    stand.disturb()

                                    dist_stand.dist = dist
                                    dist_stand.area = disturbed_area
                                    dist_stand.species = species
                                    dist_stand.yield_class = yield_class
                                    dist_stand.soil = soil
                                    self.disturbed_stands.append(dist_stand)

                                elif stand.since_last_dist < self.disturbance_timing.loc[mask, "min years since dist"].item():
                                        
                                    stand.reset_dist()
           
                    

    def get_stand_data_for_year(self):
        """Returns a list of tuples containing stand data for the current year."""
        return [(stand.species, stand.yield_class, stand.soil, stand.area, stand.age, stand.since_last_dist) for stand in self.stands]
    
    def get_disturbance_data_for_year(self):
        """Returns a list of tuples containing disturbance data for the current year."""
        return [(stand.species, stand.yield_class, stand.soil, stand.area, stand.year, stand.dist) for stand in self.disturbed_stands]
    
    def get_stand_data_by_age(self):
        """Returns a nested dictionary with areas grouped by age, species, and yield class."""
        age_dict = {}

        for stand in self.stands:
            if stand.age not in age_dict:
                age_dict[stand.age] = {}

            age_species = age_dict[stand.age]

            if stand.species not in age_species:
                age_species[stand.species] = {}

            age_species_yield_class = age_species[stand.species]

            if stand.yield_class not in age_species_yield_class:
                age_species_yield_class[stand.yield_class] = stand.area
            else:
                age_species_yield_class[stand.yield_class] += stand.area

        return age_dict
    

