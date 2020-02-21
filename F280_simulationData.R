library(data.table)
library(dplyr)
library(tidyr)
library(gtools)
library(rjson)
library(purrr)


setwd("Q:/Shared drives/APHIS  Private Data/Pathways/data_cleaning")

F280 <- fread("Q:/Shared drives/APHIS  Private Data/Pathways/F280_CF_FY2014_to_FY2018.csv")

# Add column for data cleaning (FALSE/TRUE), FALSE - do not use, TRUE - use
F280$CLEAN <- "TRUE"

# Add notes column to document reason for omitting records, or what has been changed
F280$NOTES <- ""

# Change US origin to correct origin (based on guidance from APHIS). All remaining USA origin changed to clean=F
F280[ORIGIN_NM=="United States of America"][LOCATION=="MI Port Huron CBP"]$NOTES <- "Changed origin from US to Canada. Port Huron POE."
F280[ORIGIN_NM=="United States of America"][COMMODITY=="Aspidistra"]$NOTES <- "Changed origin from US to Netherlands. Aspidistra."
F280[ORIGIN_NM=="United States of America"][LOCATION=="MI Port Huron CBP"]$ORIGIN_NM <- "Canada"
F280[ORIGIN_NM=="United States of America"][COMMODITY=="Aspidistra"]$ORIGIN_NM <- "Netherlands"
F280[ORIGIN_NM=="United States of America"]$NOTES <- "USA origin"
F280[ORIGIN_NM=="United States of America"]$CLEAN <- "FALSE"

# Import Plantae Kingdom taxonomy from ITIS (https://www.itis.gov/hierarchy.html)
jsonFamily <- fromJSON(file="familyDict.json")
jsonOrder <- fromJSON(file="orderDict.json")
jsonClass <- fromJSON(file="classDict.json")

familyDF <- ldply(jsonFamily, data.frame, stringsAsFactors = F)
names(familyDF) <- c("Family", "Genus")

# Omit duplicate genus synonym names
genusCt <- count(familyDF, Genus)
dupGenus <- as.data.table(genusCt)[n > 1,]

familyDF_noDup <- familyDF[!familyDF$Genus %in% dupGenus$x,]

# Merge taxonomic family data to F280 records
F280_merge <- merge(F280, familyDF_noDup, by.x="COMMODITY", by.y = "Genus", all.x = TRUE)

# Export list of genuses without family match with at least 300 records and manually specify family
missingGenus <- F280_merge[is.na(Family)][CLEAN=="TRUE"]
countGenus <- count(missingGenus, COMMODITY)
addGenus <- countGenus[countGenus$n > 300,]
names(addGenus) <- c("Genus", "freq")
#write.csv(addGenus, "addGenus.csv")

addGenus$Family <- c("Orchidaceae","Orchidaceae","Asparagaceae","Asparagaceae","Bruniaceae","Alstroemeriaceae","Caryophyllaceae",
                     "Caryophyllaceae","Liliaceae","Mixed", "Asteraceae", "Rosaceae", "Acanthaceae", "Bruniaceae","Plumbaginaceae", "Asteraceae","Asteraceae",
                     "Asparagaceae","Caryophyllaceae","Asphodelaceae", "Asparagaceae",  "Onagraceae", "Hydrangeaceae","Proteaceae", "Amaryllidaceae", "Gentianaceae","Brassicaceae",
                     "Orchidaceae", "Apiaceae", "Asteraceae","Arecaceae", "Cyperaceae", "Orchidaceae", "Asparagaceae","Colchicaceae",
                     "Proteaceae","", "Asteraceae", "Stemonaceae", "Apocynaceae", "Campanulaceae", "Asphodelaceae")

addGenus$Genus <- as.character(addGenus$Genus)
addGenus <- addGenus[,c(1,3)]

familyDF_noDup <- rbind(familyDF_noDup, addGenus)

F280_merge <- merge(F280, familyDF_noDup, by.x = "COMMODITY", by.y = "Genus", all.x = TRUE)
missingGenus <- F280_merge[is.na(Family)][CLEAN=="TRUE"]

# Add order and class 
# 
# orderDF <- ldply(jsonOrder, data.frame, stringsAsFactors = F)
# names(orderDF) <- c("Order", "Family")
# 
# classDF <- ldply(jsonClass, data.frame, stringsAsFactors = F)
# names(classDF) <- c("Class", "Order")
# 
# taxoDF <- merge(orderDF, classDF, by = "Order", all.x = T)
# 
# F280_merge <- merge(F280_merge, taxoDF, by = "Family", all.x = T)
# F280_merge[Family == "Mixed",]$Order <- "Mixed"
# F280_merge[Family == "Mixed",]$Class <- "Mixed"

F280 <- F280_merge
F280[is.na(Family)]$Family <- ""
F280[Family == ""][CLEAN=="TRUE"]$NOTES <- "Unmatched Genus"
F280[Family == ""]$CLEAN <- "FALSE"

# orderCount <- as.data.table(count(F280, Order))
# names(orderCount) <- c("Order", "Count")
# orderCount[order(-orderCount$Count),]
# order_low_freq <- orderCount[Count<50]$Order # This results in 49 categories for Random Forest
# 
# F280[Order %in% order_low_freq]$CLEAN <- "FALSE"
# F280[Order %in% order_low_freq]$NOTES <- "Low freq order"


# Remove records without pathway (35), location (1299), commodity (4), or origin (150).

F280[PATHWAY==""]$CLEAN <- "FALSE"
F280[LOCATION==""]$CLEAN <- "FALSE"
F280[COMMODITY==""]$CLEAN <- "FALSE"
F280[ORIGIN_NM==""]$CLEAN <- "FALSE"
F280[PATHWAY==""]$NOTES <- "Missing PATHWAY"
F280[LOCATION==""]$NOTES <- "Missing LOCATION"
F280[COMMODITY==""]$NOTES <- "Missing COMMODITY"
F280[ORIGIN_NM==""]$NOTES <- "Missing ORIGIN_NM"

# Remove records with origin=destination, suspicious
F280[ORIGIN_NM == DEST_NM]$NOTES <- "Origin=destination"
F280[ORIGIN_NM == DEST_NM]$CLEAN <- "FALSE"

F280_clean <- droplevels(F280[CLEAN == "TRUE"])
F280_clean$PATHWAY <- as.factor(F280_clean$PATHWAY)
F280_clean$REPORT_DT <- as.Date(F280_clean$REPORT_DT)


#Small sample for testing

write.csv(F280_clean[(sample(nrow(F280_clean), 500)),c(1,3,4,5,6,7,13,16,25)], "Q:/Shared drives/APHIS  Private Data/Pathways/test_data/F280_sample.csv")

