#-----------------------------------------------------

set.seed(42)
num_pest <- 10
xrange <- yrange <- zrange <- c(0, 5)
point_col <- rgb(matrix(col2rgb(brewer.pal(5, "Purples")[4]) / 255, ncol=3), alpha=0.5)

library(purrr)

# create random data
x_rand <- rdunif(num_pest, xrange[2], xrange[1])
y_rand <- rdunif(num_pest, yrange[2], yrange[1])
z_rand <- rdunif(num_pest, zrange[2], zrange[1])
df_rand <- data.frame(x=x_rand, y=y_rand, z=z_rand)

# create clustered data
x_clust <- as.integer(rnorm(num_pest, mean=mean(xrange), sd=1))
y_clust <- as.integer(rnorm(num_pest, mean=mean(yrange), sd=1))
z_clust <- as.integer(rnorm(num_pest, mean=mean(zrange), sd=1))
df_clust <- data.frame(x=x_clust, y=y_clust, z=z_clust)

# create uniform data

df_unif <- data.frame(as.integer(seq(xrange[1], xrange[2], length.out=num_pest)), as.integer(seq(yrange[1], yrange[2], length.out=num_pest)), as.integer(seq(zrange[1], zrange[2], length.out=num_pest)))
