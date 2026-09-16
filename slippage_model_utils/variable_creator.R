# © 2026 The Johns Hopkins University Applied Physics Laboratory LLC
# Suppress startup messages
options(warn = -1)
suppressPackageStartupMessages({
  library(jsonlite)
  library(stringr)
  library(dplyr)
  library(arrow)  # For Parquet support
  library(data.table)
})

######################################################
# ===== Parse Command Line Arguments Functions ===== #
######################################################

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  cat(toJSON(list(
    error = "Expected exactly one argument (JSON file path)",
    status = "error"
  ), auto_unbox = TRUE))
  quit(status = 1)
}

json_path <- args[1]

# Read payload from JSON file
if (!file.exists(json_path)) {
  cat(toJSON(list(
    error = paste("JSON file not found:", json_path),
    status = "error"
  ), auto_unbox = TRUE))
  quit(status = 1)
}

# Parse JSON input from file
input <- tryCatch({
  fromJSON(json_path, simplifyVector = FALSE)
}, error = function(e) {
  cat(toJSON(list(
    error = paste("Failed to parse JSON file:", e$message),
    status = "error",
    json_path = json_path
  ), auto_unbox = TRUE))
  quit(status = 1)
})

# Validate input structure
if (is.null(input$func_name)) {
  cat(toJSON(list(
    error = "Missing 'func_name' field in input",
    status = "error",
    input_keys = names(input)
  ), auto_unbox = TRUE))
  quit(status = 1)
}

# Extract components
func_name <- as.character(input$func_name)
func_args <- input$args
df_args <- input$df_args
use_parquet <- if (!is.null(input$use_parquet)) input$use_parquet else FALSE

#######################################################
# ===== Helper Functions for File I/O to Python ===== #
######################################################

# Read DataFrames from file paths (Parquet or CSV)
read_df_args <- function(df_paths, use_parquet) {
  dfs <- list()
  if (!is.null(df_paths) && length(df_paths) > 0) {
    for (arg_name in names(df_paths)) {
      file_path <- df_paths[[arg_name]]
      if (!file.exists(file_path)) {
        stop(paste("File not found:", file_path))
      }

      # Auto-detect format from extension or use_parquet flag
      if (use_parquet || grepl("\\.parquet$", file_path, ignore.case = TRUE)) {
        dfs[[arg_name]] <- as.data.frame(read_parquet(file_path))
      } else {
        dfs[[arg_name]] <- read.csv(file_path, stringsAsFactors = FALSE)
      }
    }
  }
  return(dfs)
}

# Write result DataFrames to temp files
write_result_dfs <- function(result, use_parquet, temp_dir = NULL) {
  df_results <- list()
  cleaned_result <- list()

  for (name in names(result)) {
    value <- result[[name]]
    if (is.data.frame(value)) {
      # Write DataFrame to temp file in Python's temp directory
      if (is.null(temp_dir)) {
        # Fallback to R's temp dir (but this causes the issue!)
        temp_dir <- tempdir()
      }

      if (use_parquet) {
        temp_file <- file.path(temp_dir, paste0(name, "_", format(Sys.time(), "%Y%m%d_%H%M%S"), ".parquet"))
        write_parquet(value, temp_file)
      } else {
        temp_file <- file.path(temp_dir, paste0(name, "_", format(Sys.time(), "%Y%m%d_%H%M%S"), ".csv"))
        write.csv(value, temp_file, row.names = FALSE)
      }
      df_results[[name]] <- temp_file
    } else {
      cleaned_result[[name]] <- value
    }
  }

  # Add file paths to result
  if (length(df_results) > 0) {
    cleaned_result$df_results <- df_results
  }

  return(cleaned_result)
}

###################################
### ===== Helper Functions ===== ##
###################################

run_fixed_preprocessing <- function( dat, rbs.start.date, rbs.end.date )
{
  #
  # Goal: establish copy of data that is properly filtered that is not changed.
  # Filtering:
  #   - Select data within specified time frame
  #   - PM type != tissue culture (pre-specified as highest-compliance)
  #   - - Quantity units == Plant Units
  # Filtering to a restricted time, plant unit-quantities only
  dat_time <- dat %>%
    filter(INSPECTION_DATETIME >= as.Date(rbs.start.date) &
             INSPECTION_DATETIME <= as.Date(rbs.end.date) )
  dat_filtered <- dat_time %>%
    filter(PROPAGATIVE_MATERIAL_TYPE != "Meristem or Callus Tissue Culture (micropropagated/in vitro culture)",
           QUANTITY_UNITS_NAME %in% "Plant Units")
  # Basic text preprocessing
  setDT(dat_filtered)
  dat_filtered[, IMPORTER_NAME1 := basic_text_preproc(dat_filtered$IMPORTER_NAME)]
  dat_filtered[, PRODUCER_NAME1 := basic_text_preproc(dat_filtered$PRODUCER_NAME)]

  return(dat_filtered)
}



remove_extra_chars <- function(suffix_string, prefix_string, text) {
  text <- gsub(suffix_string, "", text)
  text <- gsub(prefix_string, "", text)
  text <- str_squish(text)
  return(text)
}

top_strata_fit <- function(df, tbl_col,
                           maxStratCount = NULL,
                           minActionRate = NULL,
                           minRecords    = NULL,
                           rank_by = c("action_rate", "count", "action_count")) {

  rank_by <- match.arg(rank_by)

  stopifnot(tbl_col %in% names(df))
  stopifnot("action" %in% names(df))

  x <- df[[tbl_col]]
  y <- as.integer(df[["action"]])

  tmp <- data.frame(level = as.character(x), action = y, stringsAsFactors = FALSE)
  agg <- aggregate(action ~ level, data = tmp, FUN = function(z) c(n = length(z), sum = sum(z)))
  agg$count <- agg$action[, "n"]
  agg$action_sum <- agg$action[, "sum"]
  agg$action <- NULL
  agg$action_rate <- agg$action_sum / agg$count

  if (!is.null(minActionRate)) agg <- agg[agg$action_rate >= minActionRate, , drop = FALSE]
  if (!is.null(minRecords))    agg <- agg[agg$count >= minRecords, , drop = FALSE]

  if (!is.null(maxStratCount)) {
    if (rank_by == "action_rate") {
      agg <- agg[order(-agg$action_rate), , drop = FALSE]
    } else if (rank_by == "count") {
      agg <- agg[order(-agg$count), , drop = FALSE]
    } else { # action_count (matches your old function best)
      agg <- agg[order(-agg$action_sum, -agg$count, -agg$action_rate), , drop = FALSE]
    }
    agg <- head(agg, maxStratCount)
  }

  list(keep_levels = agg$level, summary = agg)
}



top_strata_apply <- function(df, tbl_col, keep_levels,
                             ref = "Reference", missing = "missing",
                             train_levels = NULL) {
  stopifnot(tbl_col %in% names(df))
  x <- df[[tbl_col]]

  x_chr <- as.character(x)
  x_chr[is.na(x_chr) | x_chr == ""] <- missing
  x_chr[!(x_chr %in% keep_levels)] <- ref

  # Make factor with consistent levels across datasets
  if (is.null(train_levels)) {
    levs <- sort(unique(c(keep_levels, ref, missing)))
  } else {
    levs <- train_levels
  }

  factor(x_chr, levels = levs)
}


get_name_groups <- function(x) {
  # entity resolution function to replace names from a table with group names.
  #  The function replaces each name with the shortest name in its group.
  #  The function should normally be called after basic preprocessing such as
  #   making names lower case, removing punctuation as in the function
  #   'basic_text_preproc()'
  #  The resultant group variable is to be used as a model predictor in place
  #    of the original set of ungrouped names
  # Input: The argument x is a 2-column matrix, with names in 1st column,
  #         code numbers in 2nd column
  # Output: a 3-column data frame whose first two columns are the input columns,
  #         and the 3rd column is group names to be used for modeling
  # For the code numbers, positive numbers are group numbers. Zero or negative
  #  numbers indicate that the the corresponding name is not grouped with others
  #### Format x as a data frame with fixed column names
  x <- as.data.frame(x, stringsAsFactors = FALSE)
  if (ncol(x) != 2) stop("Input must have exactly 2 columns.")
  names(x) <- c("str", "grp")
  x$str <- as.character(x$str)
  x$grp <- as.numeric(x$grp)
  setDT(x)
  #### Function to find the shortest name in each group:
  pick_shortest <- function(v) {
    v <- as.character(v)
    v <- v[!is.na(v)]
    if (length(v) == 0) return(NA_character_)
    m <- min(nchar(v))
    sort(v[nchar(v) == m])[1]
  }
  #### Make corrections for repeated negative group numbers that should be grouped
  next_group_nr <- max(x$grp) + 1
  group_nr_counts <- x[grp<0, .(grp_count = .N), by = grp][grp_count > 1]
  negative_groups_to_merge <- group_nr_counts |> pull(grp)
  for (j in 1:length(negative_groups_to_merge)) {
    x[grp == negative_groups_to_merge[j], grp := next_group_nr]
    next_group_nr <- next_group_nr + 1
  }
  #### Apply pick_shortest() to compute group names for positive group numbers
  group_name <- tapply(
    x$str[x$grp > 0],
    x$grp[x$grp > 0],
    pick_shortest
  )
  #### Default: group name is the original string
  x$group_name <- x$str

  #### Replace only where group number is positive
  positive <- which(x$grp > 0)
  x$group_name[positive] <- unname(group_name[as.character(x$grp[positive])])

  # Sort by original strings
  o <- order(x$str, na.last = TRUE)
  out <- data.frame(
    string = x$str[o],
    grp    = x$grp[o],
    group  = x$group_name[o],
    stringsAsFactors = FALSE
  )
  setDT(out)
  colnames(out) <- c("name", "group number", "group")
  out
}



###################################################
### ===== Main Functions Called by Python ===== ###
###################################################

# ===== Basic Text Pre-Processing Function ===== #
basic_text_preproc <- function(text_field, suffix_string = NULL, prefix_string = NULL) {
  text <- text_field
  text <- tolower(text)
  text[is.na(text) | text == "not selected"] <- "missing"
  text <- gsub("[[:punct:]]+", "", text)

  # Drop end of producer names beginning with "box"
  ndx_box1 <- regexpr("box", text) - 1
  ndx_box1 <- ifelse(ndx_box1 > 0, ndx_box1, nchar(text))
  text <- substring(text, 1, ndx_box1)  # << fix here

  # Drop stand-alone numbers
  text <- str_remove_all(text, "\\b\\d+\\b")

  # Drop leading & trailing blanks, replace strings of blanks with a single blank
  text <- str_squish(text)

  # Drop known uninformative prefix and suffix strings
  if (is.null(suffix_string)) {
    suffix_string <- " sa| s a|sociedad anonima| inc| llc| ltd| ltda| cv| rl| co| co ltd| corp| bv| b v| corporation| company| limited"
    suffix_string <- paste0(gsub("\\|", "$|", suffix_string), "$")
  }
  if (is.null(prefix_string)) {
    prefix_string <- "mr |m r "
    prefix_string <- paste0("^", gsub("\\|", "|^", prefix_string))
  }

  text <- remove_extra_chars(suffix_string = suffix_string,
                             prefix_string = prefix_string, text)

  return(list(
    processed_text = text,
    status = "success"
  ))
}




# ===== Producer Mapping ===== #
entity_resolution <- function(dt, entity_resolution_lookup_table) {

    # Convert to data.table
  dt <- as.data.table(dt)
  entity_resolution_lookup_table <- as.data.table(entity_resolution_lookup_table)

  entity_resolution_lookup_table <- get_name_groups(entity_resolution_lookup_table[, .(name, group)])

  # Left join and create grouped user names
  dt[
    entity_resolution_lookup_table,
    PRODUCER_GROUP_NAME := fcoalesce(i.group, PRODUCER_NAME),
    on = .(PRODUCER_NAME = name)
  ]

  # choose producer name with largest quantity per modeling unit
  tot <- dt[, .(total_quantity = sum(QUANTITY), nr_rows = .N),
                      by = .(COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE, INSPECTION_NUMBER, PRODUCER_GROUP_NAME)]
  best1 <- tot[order(-total_quantity, -nr_rows), .SD[1],
               by = .(COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE, INSPECTION_NUMBER)]
  best1 <- best1[, .(COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE, INSPECTION_NUMBER,
                     PRODUCER_GROUP_NAME_best = PRODUCER_GROUP_NAME)]
  dt <- best1[dt, on = .(COUNTRY_OF_ORIGIN_NAME, PROPAGATIVE_MATERIAL_TYPE, INSPECTION_NUMBER)]
  dt[, PRODUCER_GROUP_NAME1 := PRODUCER_GROUP_NAME_best][, PRODUCER_GROUP_NAME_best := NULL]

  list(result_df = dt)
}












# ===== Quantity Threshold Binary Function ===== #

generate_quantity_binaries <- function(df,
                                      quantity_threshold = 200,
                                      group_cols = c("RISK_UNIT")) {
  if (is.null(df)) {
    stop("df argument is required")
  }

  # Ensure df is a data frame
  if (!is.data.frame(df)) {
    stop("df must be a data.frame")
  }

  # Ensure QUANTITY is numeric
  if (!"QUANTITY" %in% names(df)) {
    stop(paste("QUANTITY column not found. Available columns:", paste(names(df), collapse = ", ")))
  }
  df$QUANTITY <- as.numeric(df$QUANTITY)

  # Ensure group_cols is a character vector (flatten if nested list)
  if (is.list(group_cols) && !is.data.frame(group_cols)) {
    group_cols <- unlist(group_cols, recursive = TRUE)
  }
  group_cols <- as.character(group_cols)

  # Remove any NA or empty strings
  group_cols <- group_cols[!is.na(group_cols) & nchar(group_cols) > 0]

  if (length(group_cols) == 0) {
    stop("group_cols must contain at least one valid column name")
  }

  # Ensure required columns exist
  required_cols <- c("QUANTITY", group_cols)
  missing_cols <- setdiff(required_cols, names(df))
  if (length(missing_cols) > 0) {
    available_cols <- names(df)
    stop(paste0(
      "Missing required columns: ", paste(missing_cols, collapse = ", "), "\n",
      "Available columns: ", paste(available_cols, collapse = ", ")
    ))
  }

  # Perform aggregation
  if (length(group_cols) == 1) {
    # Single grouping column
    dt <- df %>%
      group_by(.data[[group_cols[1]]]) %>%
      summarize(
        TOTAL_QTY = sum(QUANTITY, na.rm = TRUE),
        MIN_QTY = min(QUANTITY, na.rm = TRUE),
        MEDIAN_QTY = median(QUANTITY, na.rm = TRUE),
        FRAC_SMALL = mean(QUANTITY < quantity_threshold, na.rm = TRUE),
        MEDIAN_QTY_LT200 = median(QUANTITY, na.rm = TRUE) < quantity_threshold,
        FRAC_SMALL_GT07 = mean(QUANTITY < quantity_threshold, na.rm = TRUE) > 0.7,
        ANY_SMALL = as.integer(any(QUANTITY < quantity_threshold, na.rm = TRUE)),
        n_commodity_lines = n(),
        .groups = "drop"
      )
  } else {
    # Multiple grouping columns
    dt <- df %>%
      group_by(across(all_of(group_cols))) %>%
      summarize(
        TOTAL_QTY = sum(QUANTITY, na.rm = TRUE),
        MIN_QTY = min(QUANTITY, na.rm = TRUE),
        MEDIAN_QTY = median(QUANTITY, na.rm = TRUE),
        FRAC_SMALL = mean(QUANTITY < quantity_threshold, na.rm = TRUE),
        MEDIAN_QTY_LT200 = median(QUANTITY, na.rm = TRUE) < quantity_threshold,
        FRAC_SMALL_GT07 = mean(QUANTITY < quantity_threshold, na.rm = TRUE) > 0.7,
        ANY_SMALL = as.integer(any(QUANTITY < quantity_threshold, na.rm = TRUE)),
        n_commodity_lines = n(),
        .groups = "drop"
      )
  }

  # Convert to data.frame and ensure proper types
  dt <- as.data.frame(dt, stringsAsFactors = FALSE)

  # Ensure character/factor columns are converted to character
  for (col in names(dt)) {
    if (is.factor(dt[[col]])) {
      dt[[col]] <- as.character(dt[[col]])
    }
  }

  # Return as DataFrame (will be written to file by wrapper)
  return(list(result_df = dt))
}



# ===== Creating Producer Group Top Feature Function  ===== #

generate_producer_top_strata_features <- function(
  df,
  dt_train,
  maxStratCount = 50,
  minActionRate = 0.02,
  minRecords = 5
) {
#   if (is.null(df)) {
#     stop("df argument is required")
#   }
#
#   if (!is.data.frame(df)) {
#     stop("df must be a data.frame")
#   }
#
#   if (is.null(dt_train)) {
#     stop("dt_train argument is required")
#   }
#
#   if (!is.data.frame(dt_train)) {
#     stop("dt_train must be a data.frame")
#   }
#
#   required_cols <- c("action", "PRODUCER_GROUP_NAME1")
#   missing_cols <- setdiff(required_cols, names(df))
#   if (length(missing_cols) > 0) {
#     stop(paste0("Missing required columns: ", paste(missing_cols, collapse = ", ")))
#   }

  fit_prod <- top_strata_fit(
    dt_train,
    tbl_col = "PRODUCER_GROUP_NAME1",
    maxStratCount = maxStratCount,
    minActionRate = minActionRate,
    minRecords = minRecords,
    rank_by = "count"
  )

  dt_train$PRODUCER_GROUP_TOP <- top_strata_apply(
    dt_train,
    "PRODUCER_GROUP_NAME1",
    keep_levels = fit_prod$keep_levels
  )
  prod_levels <- levels(dt_train$PRODUCER_GROUP_TOP)

  df$PRODUCER_GROUP_TOP <- top_strata_apply(
    df,
    "PRODUCER_GROUP_NAME1",
    keep_levels = fit_prod$keep_levels,
    train_levels = prod_levels
  )

  #df$PRODUCER_GROUP_TOP <- as.character(df$PRODUCER_GROUP_TOP)

  list(result_df = df)
}


# ===== Creating IMPORTER_NAME_TOP Feature Function  ===== #

generate_importer_top_strata_features <- function(
  df,
  dt_train,
  maxStratCount = 50,
  minActionRate = 0.02,
  minRecords = 5
) {
  if (is.null(df)) {
    stop("df argument is required")
  }

  if (!is.data.frame(df)) {
    stop("df must be a data.frame")
  }

  if (is.null(dt_train)) {
    stop("dt_train argument is required")
  }

  if (!is.data.frame(dt_train)) {
    stop("dt_train must be a data.frame")
  }

  required_cols <- c("action", "IMPORTER_NAME1")
  missing_cols <- setdiff(required_cols, names(df))
  if (length(missing_cols) > 0) {
    stop(paste0("Missing required columns: ", paste(missing_cols, collapse = ", ")))
  }

  fit_import <- top_strata_fit(
    dt_train,
    tbl_col = "IMPORTER_NAME1",
    maxStratCount = maxStratCount,
    minActionRate = minActionRate,
    minRecords = minRecords,
    rank_by = "count"
  )
  dt_train$IMPORTER_NAME_TOP <- top_strata_apply(
    dt_train,
    "IMPORTER_NAME1",
    keep_levels = fit_import$keep_levels
  )
  import_levels <- levels(dt_train$IMPORTER_NAME_TOP)
  df$IMPORTER_NAME_TOP <- top_strata_apply(
    df,
    "IMPORTER_NAME1",
    keep_levels = fit_import$keep_levels,
    train_levels = import_levels
  )

  df$IMPORTER_NAME_TOP <- as.character(df$IMPORTER_NAME_TOP)

  list(result_df = df)
}




##################################
### ===== Main Execution ===== ###
##################################

# Read DataFrames from file paths
tryCatch({
  dfs <- read_df_args(df_args, use_parquet)

  # Extract temp directory from payload (Python will provide this)
  temp_dir <- if (!is.null(input$temp_dir)) input$temp_dir else NULL

  # Merge DataFrame arguments with simple arguments
  all_args <- c(func_args, dfs)

  # Execute the requested function
  result <- switch(
    func_name,
    "basic_text_preproc" = do.call(basic_text_preproc, all_args),
    "generate_quantity_binaries" = do.call(generate_quantity_binaries, all_args),
    "generate_producer_top_strata_features" = do.call(generate_producer_top_strata_features, all_args),
    "generate_importer_top_strata_features" = do.call(generate_importer_top_strata_features, all_args),
    "entity_resolution"              = do.call(entity_resolution, all_args),
    {
      list(
        error = paste("Unknown function:", func_name),
        status = "error",
        available_functions = c(
        "basic_text_preproc",
        "generate_quantity_binaries",
        "generate_producer_top_strata_features",
        "generate_importer_top_strata_features",
        "entity_resolution"
        )
      )
    }
  )

  # Check if result has an error status
  if (!is.null(result$status) && result$status == "error") {
    cat(toJSON(result, auto_unbox = TRUE, digits = NA, null = "null"))
    cat("\n")
    flush(stdout())
    quit(save = "no", status = 1, runLast = FALSE)
  }

  # Process result - write DataFrames to files (pass temp_dir)
  final_result <- write_result_dfs(result, use_parquet, temp_dir)

  # Output JSON to stdout
  cat(toJSON(final_result, auto_unbox = TRUE, digits = NA, null = "null"))
  cat("\n")
  flush(stdout())
  flush(stderr())

  # Explicit clean exit
  quit(save = "no", status = 0, runLast = FALSE)

}, error = function(e) {
  error_result <- list(
    error = e$message,
    status = "error",
    function_name = func_name,
    traceback = paste(capture.output(traceback()), collapse = "\n")
  )
  cat(toJSON(error_result, auto_unbox = TRUE, digits = NA, null = "null"))
  cat("\n")
  flush(stdout())
  flush(stderr())
  quit(save = "no", status = 1, runLast = FALSE)
})

quit(save = "no", status = 0, runLast = FALSE)

