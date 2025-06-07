const express = require('express');
const cors = require('cors');
const { Client } = require('@elastic/elasticsearch');
const path = require('path');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

// Elasticsearch client
const client = new Client({
  node: process.env.ELASTICSEARCH_URL || 'http://localhost:9200'
});

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Search API endpoint
app.post('/api/search', async (req, res) => {
  try {
    const { query, filters, from = 0, size = 10 } = req.body;
    
    const searchBody = {
      query: {
        bool: {
          must: [],
          filter: []
        }
      },
      from,
      size,
      sort: [
        { '_score': { order: 'desc' } },
        { 'metadata.collected_at': { order: 'desc' } }
      ],
      aggs: {
        resource_types: {
          terms: {
            field: 'type.keyword',
            size: 50
          }
        },
        sources: {
          terms: {
            field: 'metadata.source.keyword',
            size: 10
          }
        },
        terraform_version: {
          terms: {
            field: 'terraform_version.keyword',
            size: 10
          }
        }
      }
    };

    // Add search query
    if (query && query.trim()) {
      searchBody.query.bool.must.push({
        multi_match: {
          query: query,
          fields: [
            'name^3',
            'type^2',
            'attributes.*',
            'metadata.*',
            'tags.*'
          ],
          type: 'best_fields',
          fuzziness: 'AUTO'
        }
      });
    } else {
      searchBody.query.bool.must.push({
        match_all: {}
      });
    }

    // Add filters
    if (filters) {
      Object.entries(filters).forEach(([field, values]) => {
        if (values && values.length > 0) {
          searchBody.query.bool.filter.push({
            terms: {
              [`${field}.keyword`]: values
            }
          });
        }
      });
    }

    const response = await client.search({
      index: process.env.ES_INDEX || 'terraform-resources',
      body: searchBody
    });

    res.json({
      results: response.body.hits.hits.map(hit => ({
        id: hit._id,
        ...hit._source,
        _score: hit._score
      })),
      totalResults: response.body.hits.total.value,
      aggregations: response.body.aggregations
    });

  } catch (error) {
    console.error('Search error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Drill-down search endpoint
app.post('/api/drilldown', async (req, res) => {
  try {
    const { resourceId, field } = req.body;
    
    // Get the source document
    const doc = await client.get({
      index: process.env.ES_INDEX || 'terraform-resources',
      id: resourceId
    });

    const source = doc.body._source;
    const fieldValue = source[field];

    if (!fieldValue) {
      return res.json({ results: [], totalResults: 0 });
    }

    // Search for related resources
    const searchBody = {
      query: {
        bool: {
          must: [
            {
              term: {
                [`${field}.keyword`]: fieldValue
              }
            }
          ],
          must_not: [
            {
              term: {
                _id: resourceId
              }
            }
          ]
        }
      },
      size: 20
    };

    const response = await client.search({
      index: process.env.ES_INDEX || 'terraform-resources',
      body: searchBody
    });

    res.json({
      results: response.body.hits.hits.map(hit => ({
        id: hit._id,
        ...hit._source,
        _score: hit._score
      })),
      totalResults: response.body.hits.total.value,
      drilldownField: field,
      drilldownValue: fieldValue
    });

  } catch (error) {
    console.error('Drilldown error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Multi-key search endpoint
app.post('/api/multi-search', async (req, res) => {
  try {
    const { searches } = req.body; // Array of {key, value} pairs
    
    const searchBody = {
      query: {
        bool: {
          must: searches.map(({ key, value }) => ({
            multi_match: {
              query: value,
              fields: [
                `${key}^2`,
                `${key}.*`,
                `attributes.${key}^2`,
                `attributes.${key}.*`
              ],
              type: 'best_fields',
              fuzziness: 'AUTO'
            }
          }))
        }
      },
      size: 50,
      sort: [
        { '_score': { order: 'desc' } }
      ]
    };

    const response = await client.search({
      index: process.env.ES_INDEX || 'terraform-resources',
      body: searchBody
    });

    res.json({
      results: response.body.hits.hits.map(hit => ({
        id: hit._id,
        ...hit._source,
        _score: hit._score
      })),
      totalResults: response.body.hits.total.value,
      searchCriteria: searches
    });

  } catch (error) {
    console.error('Multi-search error:', error);
    res.status(500).json({ error: error.message });
  }
});

// Health check
app.get('/health', async (req, res) => {
  try {
    await client.ping();
    res.json({ status: 'healthy', elasticsearch: 'connected' });
  } catch (error) {
    res.status(500).json({ status: 'unhealthy', error: error.message });
  }
});

app.listen(port, () => {
  console.log(`Search UI server running on port ${port}`);
});