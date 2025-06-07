class TerraformSearchUI {
    constructor() {
        this.currentPage = 0;
        this.pageSize = 10;
        this.totalResults = 0;
        this.currentFilters = {};
        this.searchHistory = [];
        
        this.initializeEventListeners();
        this.performInitialSearch();
    }

    initializeEventListeners() {
        // Main search
        document.getElementById('searchBtn').addEventListener('click', () => this.performSearch());
        document.getElementById('mainSearch').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });

        // Multi-search
        document.getElementById('multiSearchBtn').addEventListener('click', () => this.performMultiSearch());
        
        // Add search item
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('add-search-item')) {
                this.addSearchItem();
            }
        });
    }

    addSearchItem() {
        const container = document.getElementById('multiSearchContainer');
        const newItem = document.createElement('div');
        newItem.className = 'multi-search-item row mb-2';
        newItem.innerHTML = `
            <div class="col-md-4">
                <input type="text" class="form-control form-control-sm search-key" placeholder="Key (e.g., type, region)">
            </div>
            <div class="col-md-6">
                <input type="text" class="form-control form-control-sm search-value" placeholder="Value">
            </div>
            <div class="col-md-2">
                <button class="btn btn-sm btn-outline-danger remove-search-item">×</button>
            </div>
        `;
        
        // Add remove functionality
        newItem.querySelector('.remove-search-item').addEventListener('click', () => {
            newItem.remove();
        });
        
        container.appendChild(newItem);
    }

    async performSearch(page = 0) {
        const query = document.getElementById('mainSearch').value;
        this.currentPage = page;
        
        await this.search({
            query,
            filters: this.currentFilters,
            from: page * this.pageSize,
            size: this.pageSize
        });
    }

    async performMultiSearch() {
        const searchItems = document.querySelectorAll('.multi-search-item');
        const searches = [];
        
        searchItems.forEach(item => {
            const key = item.querySelector('.search-key').value.trim();
            const value = item.querySelector('.search-value').value.trim();
            if (key && value) {
                searches.push({ key, value });
            }
        });

        if (searches.length === 0) {
            alert('Please enter at least one key-value pair for multi-search');
            return;
        }

        try {
            this.showLoading(true);
            const response = await fetch('/api/multi-search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ searches })
            });

            const data = await response.json();
            this.displayResults(data.results, data.totalResults);
            this.displaySearchCriteria(data.searchCriteria);
            
        } catch (error) {
            console.error('Multi-search error:', error);
            this.showError('Failed to perform multi-search');
        } finally {
            this.showLoading(false);
        }
    }

    async performInitialSearch() {
        await this.search({
            query: '',
            filters: {},
            from: 0,
            size: this.pageSize
        });
    }

    async search(searchParams) {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(searchParams)
            });

            const data = await response.json();
            
            if (data.error) {
                throw new Error(data.error);
            }

            this.displayResults(data.results, data.totalResults);
            this.displayFacets(data.aggregations);
            this.updatePagination(data.totalResults);
            
        } catch (error) {
            console.error('Search error:', error);
            this.showError('Failed to search resources');
        } finally {
            this.showLoading(false);
        }
    }

    displayResults(results, total) {
        this.totalResults = total;
        const container = document.getElementById('resultsContainer');
        const countElement = document.getElementById('resultsCount');
        
        countElement.textContent = total > 0 ? 
            `Found ${total} resource${total !== 1 ? 's' : ''}` : 
            'No resources found';

        if (results.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="fas fa-search fa-3x mb-3"></i>
                    <h4>No resources found</h4>
                    <p>Try adjusting your search terms or filters.</p>
                </div>
            `;
            return;
        }

        const html = results.map(resource => this.createResourceCard(resource)).join('');
        container.innerHTML = html;
    }

    createResourceCard(resource) {
        const tags = resource.tags ? Object.entries(resource.tags)
            .map(([key, value]) => `<span class="badge bg-secondary tag-badge">${key}:${value}</span>`)
            .join('') : '';

        const metadata = resource.metadata || {};
        const source = metadata.source || 'unknown';
        const sourceIcon = this.getSourceIcon(source);

        return `
            <div class="card resource-card mb-3" onclick="terraformUI.showResourceDetails('${resource.id}')">
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-8">
                            <h5 class="card-title">
                                <i class="fas fa-cube text-primary"></i>
                                ${resource.name || 'Unnamed Resource'}
                                ${resource._score ? `<small class="text-muted">(score: ${resource._score.toFixed(2)})</small>` : ''}
                            </h5>
                            <h6 class="card-subtitle mb-2 text-muted">
                                <i class="${sourceIcon}"></i> ${resource.type} 
                                <span class="badge bg-light text-dark">${source}</span>
                            </h6>
                            <div class="mb-2">${tags}</div>
                        </div>
                        <div class="col-md-4 text-end">
                            <div class="btn-group-vertical" role="group">
                                <button class="btn btn-sm btn-outline-primary drill-down-btn" 
                                        onclick="event.stopPropagation(); terraformUI.drillDown('${resource.id}', 'type')"
                                        title="Find similar resources">
                                    <i class="fas fa-sitemap"></i> Similar Type
                                </button>
                                ${resource.attributes && resource.attributes.region ? 
                                    `<button class="btn btn-sm btn-outline-secondary drill-down-btn" 
                                             onclick="event.stopPropagation(); terraformUI.drillDown('${resource.id}', 'attributes.region')"
                                             title="Find resources in same region">
                                        <i class="fas fa-globe"></i> Same Region
                                    </button>` : ''
                                }
                                ${metadata.bucket ? 
                                    `<button class="btn btn-sm btn-outline-info drill-down-btn" 
                                             onclick="event.stopPropagation(); terraformUI.drillDown('${resource.id}', 'metadata.bucket')"
                                             title="Find resources from same source">
                                        <i class="fas fa-database"></i> Same Source
                                    </button>` : ''
                                }
                            </div>
                        </div>
                    </div>
                    <div class="mt-2">
                        <small class="text-muted">
                            <i class="fas fa-clock"></i> 
                            ${metadata.collected_at ? new Date(metadata.collected_at).toLocaleString() : 'Unknown time'}
                        </small>
                    </div>
                </div>
            </div>
        `;
    }

    getSourceIcon(source) {
        const icons = {
            's3': 'fab fa-aws',
            'filesystem': 'fas fa-folder',
            'kubernetes': 'fas fa-dharmachakra',
            'unknown': 'fas fa-question-circle'
        };
        return icons[source] || icons.unknown;
    }

    displayFacets(aggregations) {
        if (!aggregations) return;

        const container = document.getElementById('facetsContainer');
        let html = '';

        Object.entries(aggregations).forEach(([facetName, facetData]) => {
            const displayName = this.getFacetDisplayName(facetName);
            const buckets = facetData.buckets || [];
            
            if (buckets.length > 0) {
                html += `
                    <div class="facet-group mb-3">
                        <h6>${displayName}</h6>
                        ${buckets.slice(0, 10).map(bucket => `
                            <div class="facet-item">
                                <label class="form-check-label d-flex justify-content-between">
                                    <div>
                                        <input type="checkbox" class="form-check-input me-2" 
                                               onchange="terraformUI.toggleFilter('${facetName}', '${bucket.key}', this.checked)">
                                        ${bucket.key}
                                    </div>
                                    <span class="badge bg-light text-dark">${bucket.doc_count}</span>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        });

        container.innerHTML = html;
    }

    getFacetDisplayName(facetName) {
        const names = {
            'resource_types': 'Resource Types',
            'sources': 'Sources',
            'terraform_version': 'Terraform Version'
        };
        return names[facetName] || facetName;
    }

    toggleFilter(facetName, value, isChecked) {
        const filterKey = facetName.replace('_types', '').replace('resource_', '');
        
        if (!this.currentFilters[filterKey]) {
            this.currentFilters[filterKey] = [];
        }

        if (isChecked) {
            if (!this.currentFilters[filterKey].includes(value)) {
                this.currentFilters[filterKey].push(value);
            }
        } else {
            this.currentFilters[filterKey] = this.currentFilters[filterKey].filter(v => v !== value);
            if (this.currentFilters[filterKey].length === 0) {
                delete this.currentFilters[filterKey];
            }
        }

        this.performSearch(0);
    }

    async drillDown(resourceId, field) {
        try {
            const response = await fetch('/api/drilldown', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ resourceId, field })
            });

            const data = await response.json();
            this.showDrilldownResults(data.results, data.drilldownField, data.drilldownValue);
            
        } catch (error) {
            console.error('Drilldown error:', error);
            this.showError('Failed to perform drill-down search');
        }
    }

    showDrilldownResults(results, field, value) {
        const modal = new bootstrap.Modal(document.getElementById('drilldownModal'));
        const content = document.getElementById('drilldownContent');
        
        if (results.length === 0) {
            content.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="fas fa-search fa-2x mb-3"></i>
                    <h5>No related resources found</h5>
                    <p>No other resources share the same ${field}: <strong>${value}</strong></p>
                </div>
            `;
        } else {
            const html = `
                <div class="mb-3">
                    <h6><i class="fas fa-filter"></i> Resources with ${field}: <strong>${value}</strong></h6>
                    <small class="text-muted">Found ${results.length} related resource${results.length !== 1 ? 's' : ''}</small>
                </div>
                ${results.map(resource => `
                    <div class="card mb-2" onclick="terraformUI.showResourceDetails('${resource.id}')">
                        <div class="card-body py-2">
                            <h6 class="card-title mb-1">
                                <i class="fas fa-cube text-primary"></i> ${resource.name || 'Unnamed Resource'}
                            </h6>
                            <small class="text-muted">${resource.type}</small>
                        </div>
                    </div>
                `).join('')}
            `;
            content.innerHTML = html;
        }
        
        modal.show();
    }

    showResourceDetails(resourceId) {
        // This would be populated with full resource details
        const modal = new bootstrap.Modal(document.getElementById('resourceModal'));
        const details = document.getElementById('resourceDetails');
        
        details.innerHTML = `
            <div class="text-center py-4">
                <div class="spinner-border" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <p class="mt-2">Loading resource details...</p>
            </div>
        `;
        
        modal.show();
        
        // Here you would fetch and display full resource details
        setTimeout(() => {
            details.innerHTML = `
                <div class="alert alert-info">
                    <h6><i class="fas fa-info-circle"></i> Resource ID: ${resourceId}</h6>
                    <p>Full resource details would be displayed here with all attributes, relationships, and metadata.</p>
                </div>
            `;
        }, 500);
    }

    displaySearchCriteria(searchCriteria) {
        const container = document.getElementById('activeFilters');
        const chips = searchCriteria.map(({ key, value }) => 
            `<span class="search-chip">${key}: ${value}</span>`
        ).join('');
        
        container.innerHTML = `
            <div class="mb-2">
                <small class="text-muted">Active search criteria:</small><br>
                ${chips}
            </div>
        `;
    }

    updatePagination(totalResults) {
        const container = document.getElementById('paginationContainer');
        const totalPages = Math.ceil(totalResults / this.pageSize);
        
        if (totalPages <= 1) {
            container.style.display = 'none';
            return;
        }

        container.style.display = 'block';
        const pagination = container.querySelector('.pagination');
        
        let html = '';
        
        // Previous button
        html += `
            <li class="page-item ${this.currentPage === 0 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="terraformUI.performSearch(${this.currentPage - 1}); return false;">Previous</a>
            </li>
        `;
        
        // Page numbers (show up to 5 pages around current)
        const startPage = Math.max(0, this.currentPage - 2);
        const endPage = Math.min(totalPages - 1, this.currentPage + 2);
        
        for (let i = startPage; i <= endPage; i++) {
            html += `
                <li class="page-item ${i === this.currentPage ? 'active' : ''}">
                    <a class="page-link" href="#" onclick="terraformUI.performSearch(${i}); return false;">${i + 1}</a>
                </li>
            `;
        }
        
        // Next button
        html += `
            <li class="page-item ${this.currentPage >= totalPages - 1 ? 'disabled' : ''}">
                <a class="page-link" href="#" onclick="terraformUI.performSearch(${this.currentPage + 1}); return false;">Next</a>
            </li>
        `;
        
        pagination.innerHTML = html;
    }

    showLoading(show) {
        document.body.classList.toggle('loading', show);
    }

    showError(message) {
        // Simple error display - could be enhanced with toast notifications
        const container = document.getElementById('resultsContainer');
        container.innerHTML = `
            <div class="alert alert-danger" role="alert">
                <i class="fas fa-exclamation-triangle"></i> ${message}
            </div>
        `;
    }
}

// Initialize the search UI when the page loads
const terraformUI = new TerraformSearchUI();