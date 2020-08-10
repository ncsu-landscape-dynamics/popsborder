# Shipment configuration

## Synthetic shipments

```yaml
shipment:
  boxes:
    min: 1
    max: 3000
  stems_per_box:
    default: 200
    air:
      default: 200
    maritime:
      default: 200
```

```yaml
  origins:
  - Netherlands
  - Mexico
  - Israel
  - Japan
  - New Zealand
  - India
  - Tanzania
  flowers:
  - Hyacinthus
  - Rosa
  - Gerbera
  - Agapanthus
  - Aegilops
  - Protea
  - Liatris
  - Mokara
  - Anemone
  - Actinidia
  ports:
  - NY JFK CBP
  - FL Miami Air CBP
  - HI Honolulu CBP
  - AZ Phoenix CBP
  - VA Dulles CBP
  - CA San Francisco CBP
  - WA Seattle Air CBP
  - TX Brownsville CBP
  - WA Blaine CBP
```

## F280-based shipments

```yaml
shipment:
  f280_file: F280_sample.csv
  stems_per_box:
    default: 200
    air:
      default: 200
    maritime:
      default: 200
```

---

Next: [Pests](pest.md)
