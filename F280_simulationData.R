library(data.table)
library(plyr)
library(tidyr)
library(gtools)
library(rjson)
library(purrr)


setwd("G:/Shared drives/APHIS  Projects/Pathways/Data")

F280 <- fread("G:/Shared drives/APHIS  Private Data/Pathways/F280_CF_FY2014_to_FY2018.csv")

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

setwd("G:/Shared drives/APHIS  Private Data/Pathways/Summaries")
# Import Plantae Kingdom taxonomy from ITIS (https://www.itis.gov/hierarchy.html)
jsonFamily <- fromJSON(file="familyDict.json")
jsonOrder <- fromJSON(file="orderDict.json")
jsonClass <- fromJSON(file="classDict.json")

familyDF <- ldply(jsonFamily, data.frame, stringsAsFactors = F)
names(familyDF) <- c("Family", "Genus")

# Merge taxonomic family data to F280 records
F280_merge <- merge(F280, familyDF, by.x="COMMODITY", by.y = "Genus", all.x = TRUE)

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

orderDF <- ldply(jsonOrder, data.frame, stringsAsFactors = F)
names(orderDF) <- c("Order", "Family")

classDF <- ldply(jsonClass, data.frame, stringsAsFactors = F)
names(classDF) <- c("Class", "Order")

taxoDF <- merge(orderDF, classDF, by = "Order", all.x = T)

F280_merge <- merge(F280_merge, taxoDF, by = "Family", all.x = T)
F280_merge[Family == "Mixed",]$Order <- "Mixed"
F280_merge[Family == "Mixed",]$Class <- "Mixed"

F280 <- F280_merge
F280[is.na(Family)]$Family <- ""
F280[Family == ""][CLEAN=="TRUE"]$NOTES <- "Unmatched Genus"
F280[Family == ""]$CLEAN <- "FALSE"

orderCount <- as.data.table(count(F280, Order))
names(orderCount) <- c("Order", "Count")
orderCount[order(-orderCount$Count),]
order_low_freq <- orderCount[Count<50]$Order # This results in 49 categories for Random Forest

F280[Order %in% order_low_freq]$CLEAN <- "FALSE"
F280[Order %in% order_low_freq]$NOTES <- "Low freq order"

# Add columns for grouped disposition codes
disp_lookup <- read.csv("disp_group_lookup.csv")
F280 <- join(F280, disp_lookup, by = "DISP_CD")

# Exclude disposition codes from analysis
F280[Include != "Y"]$CLEAN <- "FALSE"

# Which records have CFRP disposition codes but should not?
CFRP_DISP <- c("REAR", "IRAR", "DEAR", "FUAR", "OTAR", "RXAR")
CFRP_countries <- c("Colombia", "Ecuador", "Dominican Republic", "Costa Rica")
CFRP_POE <- c("TX Houston Air CBP", "GA Atlanta CBP", "NY JFK Air Cargo CBP", "NY JFK CBP", 
              "CA Los Angeles CBP", "FL Miami Air CBP", "FL Miami Air Cargo CBP", "PR San Juan Air CBP")
CFRP_commodoties <- c("Dianthus", "Liatris", "Lilium", "Rosa", "Bouquet, Rose", "Zantedeschia")
CFRP_omit <- F280[DISP_CD %in% CFRP_DISP][!(ORIGIN_NM %in% CFRP_countries)][!(LOCATION %in% CFRP_POE)][!(COMMODITY %in% CFRP_commodoties)]
F280$CLEAN[F280$F280_ID %in% CFRP_omit$F280_ID] <- "FALSE"
F280$NOTES[F280$F280_ID %in% CFRP_omit$F280_ID] <- "CFRP disp code but not in CFRP"

#CFRP_omit_summary <- CFRP_omit[,.N, by = .(ORIGIN_NM, COMMODITY)]
#write.csv(CFRP_omit_summary, "CFRP_omit_summary.csv")

# Which records have preclearance disp code but should not?
Preclear_DISP <- c("PCIR", "PCNA")
Preclear_countries <- c("Jamaica", "Chile")
# All commodities from Chile are precleared. Need to filter out some commodities from Jamaica.See CF manual pg 50
Preclear_commodities <- c("Alpinia", "Anthurium", "Croton", "Cordyline", "Cyperus","Dracaena",  "Gerbera",
                          "Gladiolus", "Heliconia", "Pandanus", "Phaeomeria", "Rosa", "Rumohra", "Strelitzia reginae")
Preclear_families <- c("Orchidaceae")
Preclear_omit <-  F280[DISP_CD %in% Preclear_DISP][!(ORIGIN_NM %in% Preclear_countries)][!(COMMODITY %in% Preclear_commodities | Family == "Orchidaceae")]
F280$CLEAN[F280$F280_ID %in% Preclear_omit$F280_ID] <- "FALSE"
F280$NOTES[F280$F280_ID %in% Preclear_omit$F280_ID] <- "Not preclearance"

#Preclear_omit_summary <- Preclear_omit[,.N, by = .(ORIGIN_NM, COMMODITY)]
#write.csv(Preclear_omit_summary, "Preclear_omit_summary.csv")

# Remove records without disposition code (n=5), pathway (35), location (1299), commodity (4), or origin (150).
# 1,423 records removed in total (some records had missing values in multiple columns)
F280[DISP_CD==""]$CLEAN <- "FALSE"
F280[PATHWAY==""]$CLEAN <- "FALSE"
F280[LOCATION==""]$CLEAN <- "FALSE"
F280[COMMODITY==""]$CLEAN <- "FALSE"
F280[ORIGIN_NM==""]$CLEAN <- "FALSE"
F280[DISP_CD==""]$NOTES <- "Missing DISP_CD"
F280[PATHWAY==""]$NOTES <- "Missing PATHWAY"
F280[LOCATION==""]$NOTES <- "Missing LOCATION"
F280[COMMODITY==""]$NOTES <- "Missing COMMODITY"
F280[ORIGIN_NM==""]$NOTES <- "Missing ORIGIN_NM"

# Remove records with origin=destination, suspicious
F280[ORIGIN_NM == DEST_NM]$NOTES <- "Origin=destination"
F280[ORIGIN_NM == DEST_NM]$CLEAN <- "FALSE"

F280_clean <- droplevels(F280[CLEAN == "TRUE"])
F280_clean$PATHWAY <- as.factor(F280_clean$PATHWAY)
F280_clean$Order <- as.factor(F280_clean$Order)
F280_clean$Class <- as.factor(F280_clean$Class)

write.csv(F280_clean, "Q:/Team Drives/APHIS  Private Data/Pathways/F280_clean.csv")

# Sample data
F280_clean <- fread("Q:/Team Drives/APHIS  Private Data/Pathways/F280_clean.csv")

#Small sample for testing
F280_clean$REPORT_DT <- as.Date(F280_clean$REPORT_DT)
write.csv(F280_clean[1:50,c(1,2,4,5,6,7,8,14,17,26,27)], "G:/Shared drives/APHIS  Private Data/Pathways/test_data/F280_sample.csv")

#F280_2018 <- F280_clean[FY=="2018"]
F280_clean[MON == 7,sum(as.numeric(QUANTITY))]



library(lubridate)

F280_clean <- separate(data = F280_clean, col = REPORT_DT, into = c("DATE", "TIME"), sep = " ")
F280_clean$DATE <- as.Date(gsub('-', '/', F280_clean$DATE))
F280_clean <-F280_clean %>%
  mutate(DATE = as_datetime(format(DATE,"2017-%m-%d")))
F280_clean$FY <- as.character(F280_clean$FY)

F280_clean$DATE <- as.Date(F280_clean$DATE)

outcome_order <- c("AP", "PA", "PC", "CC", "PP", "NP")

require(gdata)
F280_clean$Outcome <- reorder.factor(F280_clean$Outcome, new.order=outcome_order)

#write.csv(F280_2018, "G:/Team Drives/APHIS  Private Data/Pathways/F280_2018.csv")

library(dplyr)

library(ggplot2)

# Bubble chart
set.seed(89)
F280_sample <- sample_n(F280_clean, 100000)
F280_sample <- separate(data = F280_sample, col = REPORT_DT, into = c("DATE", "TIME"), sep = " ")
F280_sample$DATE <- as.Date(gsub('-', '/', F280_sample$DATE))
F280_sample <-F280_sample %>%
  mutate(DATE = as_datetime(format(DATE,"2017-%m-%d")))
F280_sample$FY <- as.character(F280_sample$FY)

#write.csv(F280_sample, "/home/kellyn/Desktop/pathways/F280_sample.csv")

F280_clean$DATE <- as.Date(F280_clean$DATE)
F280_clean$DATE <- as.Date(F280_clean$DATE)

plot_template_F280 <- ggplot(F280_sample, aes(y=as.numeric(FY))) +
  geom_hline(yintercept = seq(2014, 2018, by = 1), color = "gray", size = 0.05) +
  scale_size_area(max_size = 10, guide = FALSE) +
  scale_x_date(date_breaks = "months", date_labels = "%b") +
  scale_y_reverse(limits = c(2018,2014)) +
  xlab("") +
  ylab("")

F280_bubble<- plot_template_F280 +
  geom_point(aes(size = QUANTITY, x = DATE, color = Outcome),alpha=0.5)+theme(legend.position = "bottom",
  legend.box = "vertical") +guides(size = guide_legend(order = 4)) + scale_color_hue(labels = c("Actionable Pest", 
  "No Pest","Precautionary Action", "Product Contaminated", "Carrier Contaminated"))

F280_bubble

F280_clean <- as.data.table(F280_clean)[QUANTITY < 10000000,]
F280_2018 <- F280_clean[FY==2018]
F280_2018 <- droplevels(F280_2018)

outcomeNames <- c("No Pest", "Actionable Pest", "Precautionary", "Prohibited", "Contaminated")
outcomeAbbv <- as.data.frame(unique(F280_2018$Outcome))
outcomeAbbv$Outcome <- outcomeNames
names(outcomeAbbv) <- c("abbv", "Outcome")


F280_2018_dash <- F280_2018[, c(3, 4, 5, 6, 15, 19, 28, 30,21, 32, 33, 35, 36, 41, 44, 48)]
F280_2018_dash <- merge(F280_2018_dash, outcomeAbbv, by.x = "Outcome", by.y = "abbv")
F280_2018_dash <- select(F280_2018_dash, -c(Outcome))
F280_2018_dash <- F280_2018_dash %>% rename(Outcome = Outcome.y)

reg_high_freq <- as.character(F280_2018_dash[, .(.N), by = .(Subregion)][N>1000][[1]])
poe_high_freq <- as.character(F280_2018_dash[, .(.N), by = .(State)][N>1000][[1]])

tail(F280_2018_dash[Subregion == "South America"][order(QUANTITY)], 50)
dash_flowerRegion <- F280_2018_dash[, .(total = sum(QUANTITY), .N), by = .(Subregion, Order, Outcome)][order(-N)]
dash_flowerRegion <- dash_flowerRegion[Subregion %in% reg_high_freq]
dash_flowerRegion[Subregion=="Australia and New Zealand"]$Subregion <- "Australia"
dash_flowerPOE <- F280_2018_dash[, .(total = sum(QUANTITY), .N), by = .(State, Order, Outcome)][order(-N)]
dash_flowerPOE <- dash_flowerPOE[State %in% poe_high_freq]
dash_flowerMonth <- F280_2018_dash[, .(total = sum(QUANTITY), .N), by = .(Month, MON, Order)][order(-N)]
dash_flowerMonth <- na.omit(dash_flowerMonth)[order(MON)]
dash_flowerMonth <- dash_flowerMonth[N > 100]


write.csv(dash_flowerMonth, 'Q:/Team Drives/APHIS  Private Data/Pathways/dash_flowerMonth.csv')
write.csv(dash_flowerPOE, 'Q:/Team Drives/APHIS  Private Data/Pathways/dash_flowerPOE.csv')
write.csv(dash_flowerRegion, 'Q:/Team Drives/APHIS  Private Data/Pathways/dash_flowerRegion.csv')

# 2018 inspection outcomes quantity
ggplot(data=F280_2018, aes(x=DATE, y=QUANTITY, fill=Outcome)) + geom_col() + scale_x_date(date_breaks = "months", date_labels = "%b") +theme(legend.position = "bottom",
    legend.box = "vertical") +scale_fill_manual(values=c("red", "pink", "dodgerblue", "yellow", "lightgreen"),  labels = c("Actionable Pest","Precautionary Action", "Product Contaminated", "Product
          Prohibited", "No Pest"))+ xlab("Date") + ylab("Quantity (stems)") + ggtitle("2018 Cut Flower Shipment Inspection Outcomes")

# Inspection outcomes by order
F280_clean <- transform( F280_clean,
                       Order = ordered(Order, levels = names( sort(-table(Order)))))

ggplot(data=F280_clean, aes(x=Order, fill=Outcome)) + geom_bar(stat="count")+theme(legend.position = "bottom", legend.box = "vertical") +
    scale_fill_manual(values=c("red", "pink", "dodgerblue", "yellow", "lightgreen"),  labels = c("Actionable Pest","Precautionary Action", "Product Contaminated", "Product
    Prohibited", "No Pest"))+ xlab("Order") + ylab("Count") + ggtitle("2014-2018 Cut Flower Shipment Inspection Outcomes by Flower Order")+theme(axis.text.x = element_text(angle = 90, hjust = 1))
